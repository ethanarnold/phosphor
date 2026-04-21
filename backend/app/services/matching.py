"""Opportunity matching - rank opportunities against lab state + gap analysis."""

import re
import uuid
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab import Lab
from app.models.lab_state import LabState
from app.models.opportunity import Opportunity
from app.schemas.lab_state import LabStateData
from app.schemas.matching import (
    EquipmentStatus,
    ExpertiseStatus,
    FeasibilityBreakdown,
    GapAnalysis,
    MatchScore,
    TechniqueStatus,
)

# Keywords that suggest a piece of equipment is a standard commercial item
# a lab could reasonably acquire within a modest budget (<~$20k).
ACQUIRABLE_KEYWORDS = (
    "pcr",
    "qpcr",
    "pipette",
    "centrifuge",
    "thermocycler",
    "incubator",
    "spectrophotometer",
    "nanodrop",
    "plate reader",
    "gel",
    "balance",
    "shaker",
    "vortex",
    "rotator",
    "water bath",
    "electrophoresis",
    "light microscope",
    "fluorescence microscope",
    "inverted microscope",
    "stereo microscope",
    "dissecting microscope",
)

# Phrases that disqualify an item from being "acquirable" — expensive/specialized
# equipment that superficially matches a generic acquirable keyword.
NON_ACQUIRABLE_PHRASES = (
    "electron microscope",
    "cryo",
    "confocal",
    "mass spectrometer",
    "high-resolution mass",
    "synchrotron",
    "sequencer",
    "next-generation sequencer",
)

# Per-tier weights
_EQUIPMENT_WEIGHTS: dict[EquipmentStatus, float] = {
    "have": 1.0,
    "acquire": 0.5,
    "cannot": 0.0,
}
_TECHNIQUE_WEIGHTS: dict[TechniqueStatus, float] = {
    "practiced": 1.0,
    "learnable": 0.5,
    "gap": 0.0,
}
_EXPERTISE_WEIGHTS: dict[ExpertiseStatus, float] = {
    "strong": 1.0,
    "adjacent": 0.6,
    "gap": 0.0,
}

# Composite score weights (feasibility vs. topical alignment)
FEASIBILITY_WEIGHT = 0.6
ALIGNMENT_WEIGHT = 0.4


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation, squash whitespace."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _tokens(s: str) -> set[str]:
    return {t for t in _normalize(s).split() if len(t) > 2}


def _overlap(a: str, b: str) -> bool:
    """True if a and b clearly refer to the same thing.

    Single-token overlap isn't enough — "biology", "chemistry", "system" are
    so common they cause false positives like 'Molecular biology' matching
    'Structural biology'. Require exact match, one-string-contains-the-other,
    or Jaccard >= 0.5 on meaningful tokens.
    """
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = _tokens(na), _tokens(nb)
    if not ta or not tb:
        return False
    intersection = len(ta & tb)
    union = len(ta | tb)
    return (intersection / union) >= 0.5


def _coerce_str_list(value: object) -> list[str]:
    """required_* columns are stored as JSONB. They arrive as lists of strings
    in the normal path, but tolerate raw dicts/None defensively."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, dict):
        return [str(v) for v in value.values() if v]
    return []


def score_equipment(lab_state: LabStateData, required: list[str]) -> dict[str, EquipmentStatus]:
    """Classify each required piece of equipment against lab inventory."""
    have_names = [_normalize(e.name) for e in lab_state.equipment]
    have_caps = [_normalize(cap) for e in lab_state.equipment for cap in e.capabilities]
    result: dict[str, EquipmentStatus] = {}
    for item in required:
        norm = _normalize(item)
        if not norm:
            continue
        if any(_overlap(norm, h) for h in have_names) or any(_overlap(norm, h) for h in have_caps):
            result[item] = "have"
        elif any(blocker in norm for blocker in NON_ACQUIRABLE_PHRASES):
            result[item] = "cannot"
        elif any(kw in norm for kw in ACQUIRABLE_KEYWORDS):
            result[item] = "acquire"
        else:
            result[item] = "cannot"
    return result


def score_techniques(lab_state: LabStateData, required: list[str]) -> dict[str, TechniqueStatus]:
    """Classify each required technique against lab proficiency."""
    practiced = {
        _normalize(t.name) for t in lab_state.techniques if t.proficiency in ("expert", "competent")
    }
    learning = {_normalize(t.name) for t in lab_state.techniques if t.proficiency == "learning"}
    expertise_domains = {_normalize(e.domain) for e in lab_state.expertise}
    result: dict[str, TechniqueStatus] = {}
    for item in required:
        norm = _normalize(item)
        if not norm:
            continue
        if any(_overlap(norm, p) for p in practiced):
            result[item] = "practiced"
        elif any(_overlap(norm, p) for p in learning) or any(
            _overlap(norm, d) for d in expertise_domains
        ):
            result[item] = "learnable"
        else:
            result[item] = "gap"
    return result


def score_expertise(lab_state: LabStateData, required: list[str]) -> dict[str, ExpertiseStatus]:
    """Classify each required expertise area against lab expertise."""
    high = {_normalize(e.domain) for e in lab_state.expertise if e.confidence == "high"}
    medium = {_normalize(e.domain) for e in lab_state.expertise if e.confidence == "medium"}
    low = {_normalize(e.domain) for e in lab_state.expertise if e.confidence == "low"}
    result: dict[str, ExpertiseStatus] = {}
    for item in required:
        norm = _normalize(item)
        if not norm:
            continue
        if any(_overlap(norm, d) for d in high):
            result[item] = "strong"
        elif any(_overlap(norm, d) for d in medium) or any(_overlap(norm, d) for d in low):
            result[item] = "adjacent"
        else:
            result[item] = "gap"
    return result


def feasibility_score(breakdown: FeasibilityBreakdown) -> float:
    """Weighted average across equipment (0.4), techniques (0.4), expertise (0.2).

    Missing categories (no requirements declared) are treated as neutral 0.5
    so extraction gaps don't artificially inflate or crush the score.
    """

    def _avg(weights: dict[str, float]) -> float | None:
        if not weights:
            return None
        return sum(weights.values()) / len(weights)

    eq = _avg({k: _EQUIPMENT_WEIGHTS[v] for k, v in breakdown.equipment.items()})
    tech = _avg({k: _TECHNIQUE_WEIGHTS[v] for k, v in breakdown.techniques.items()})
    exp = _avg({k: _EXPERTISE_WEIGHTS[v] for k, v in breakdown.expertise.items()})

    parts: list[tuple[float, float]] = []
    if eq is not None:
        parts.append((eq, 0.4))
    if tech is not None:
        parts.append((tech, 0.4))
    if exp is not None:
        parts.append((exp, 0.2))

    if not parts:
        return 0.5

    total_weight = sum(w for _, w in parts)
    return sum(v * w for v, w in parts) / total_weight


def _composite(feasibility: float, alignment: float) -> float:
    return FEASIBILITY_WEIGHT * feasibility + ALIGNMENT_WEIGHT * alignment


def build_match_score(
    lab_state: LabStateData,
    opportunity: Opportunity,
    alignment: float,
) -> MatchScore:
    """Compute the full MatchScore for one opportunity."""
    breakdown = FeasibilityBreakdown(
        equipment=score_equipment(lab_state, _coerce_str_list(opportunity.required_equipment)),
        techniques=score_techniques(lab_state, _coerce_str_list(opportunity.required_techniques)),
        expertise=score_expertise(lab_state, _coerce_str_list(opportunity.required_expertise)),
    )
    feas = feasibility_score(breakdown)
    return MatchScore(
        feasibility=feas,
        alignment=alignment,
        composite=_composite(feas, alignment),
        breakdown=breakdown,
    )


async def _current_lab_state(session: AsyncSession, lab_id: uuid.UUID) -> LabState | None:
    result = await session.execute(
        select(LabState).where(LabState.lab_id == lab_id).order_by(LabState.version.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _alignment_scores(
    session: AsyncSession,
    lab_state_id: uuid.UUID,
    opportunity_ids: list[uuid.UUID],
) -> dict[uuid.UUID, float]:
    """Cosine similarity between the lab state embedding and each opportunity
    embedding, via pgvector's `<=>` operator. NULL embeddings fall back to 0.5.
    """
    if not opportunity_ids:
        return {}
    # Fetch (1 - cosine_distance) => cosine similarity in [0, 1].
    result = await session.execute(
        text(
            """
            SELECT o.id,
                   CASE
                       WHEN o.embedding IS NULL OR ls.embedding IS NULL THEN NULL
                       ELSE 1 - (ls.embedding <=> o.embedding)
                   END AS similarity
            FROM opportunities o
            CROSS JOIN (
                SELECT embedding FROM lab_states WHERE id = :ls_id
            ) ls
            WHERE o.id = ANY(:opp_ids)
            """
        ),
        {"ls_id": lab_state_id, "opp_ids": opportunity_ids},
    )
    scores: dict[uuid.UUID, float] = {}
    for opp_id, sim in result.all():
        if sim is None:
            scores[opp_id] = 0.5
        else:
            scores[opp_id] = max(0.0, min(1.0, float(sim)))
    return scores


async def rank_opportunities(
    session: AsyncSession,
    lab: Lab,
    limit: int = 50,
    min_score: float = 0.0,
    status: str = "active",
) -> list[tuple[Opportunity, MatchScore]]:
    """Rank active opportunities against the lab's current state.

    Returns scored opportunities sorted by composite score descending.
    Raises ValueError if no lab state exists (caller should surface 404).
    """
    lab_state_row = await _current_lab_state(session, lab.id)
    if lab_state_row is None:
        raise ValueError("lab has no state yet")
    lab_state_data = LabStateData.model_validate(lab_state_row.state)

    opps_result = await session.execute(
        select(Opportunity)
        .where(
            Opportunity.lab_id == lab.id,
            Opportunity.status == status,
        )
        .order_by(Opportunity.quality_score.desc().nullslast())
    )
    opportunities = list(opps_result.scalars().all())
    if not opportunities:
        return []

    alignments = await _alignment_scores(session, lab_state_row.id, [o.id for o in opportunities])

    scored: list[tuple[Opportunity, MatchScore]] = []
    for opp in opportunities:
        score = build_match_score(lab_state_data, opp, alignments.get(opp.id, 0.5))
        if score.composite >= min_score:
            scored.append((opp, score))

    scored.sort(key=lambda pair: pair[1].composite, reverse=True)
    return scored[:limit]


def _estimate_effort(
    breakdown: FeasibilityBreakdown,
) -> Literal["low", "medium", "high"]:
    """Rough effort estimate from the gap mix."""
    hard_gaps = (
        sum(1 for v in breakdown.equipment.values() if v == "cannot")
        + sum(1 for v in breakdown.techniques.values() if v == "gap")
        + sum(1 for v in breakdown.expertise.values() if v == "gap")
    )
    soft_gaps = (
        sum(1 for v in breakdown.equipment.values() if v == "acquire")
        + sum(1 for v in breakdown.techniques.values() if v == "learnable")
        + sum(1 for v in breakdown.expertise.values() if v == "adjacent")
    )
    if hard_gaps >= 3:
        return "high"
    if hard_gaps >= 1 or soft_gaps >= 3:
        return "medium"
    return "low"


async def analyze_gaps(
    session: AsyncSession,
    lab: Lab,
    opportunity_id: uuid.UUID,
) -> GapAnalysis:
    """Produce a gap analysis for one opportunity against current lab state."""
    lab_state_row = await _current_lab_state(session, lab.id)
    if lab_state_row is None:
        raise ValueError("lab has no state yet")
    lab_state_data = LabStateData.model_validate(lab_state_row.state)

    opp_result = await session.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.lab_id == lab.id,
        )
    )
    opp = opp_result.scalar_one_or_none()
    if opp is None:
        raise ValueError("opportunity not found")

    eq = score_equipment(lab_state_data, _coerce_str_list(opp.required_equipment))
    tech = score_techniques(lab_state_data, _coerce_str_list(opp.required_techniques))
    exp = score_expertise(lab_state_data, _coerce_str_list(opp.required_expertise))
    breakdown = FeasibilityBreakdown(equipment=eq, techniques=tech, expertise=exp)

    missing_equipment = [k for k, v in eq.items() if v == "cannot"]
    acquirable_equipment = [k for k, v in eq.items() if v == "acquire"]
    skill_gaps = [k for k, v in tech.items() if v == "gap"]
    learnable_skills = [k for k, v in tech.items() if v == "learnable"]
    expertise_gaps = [k for k, v in exp.items() if v == "gap"]

    # Anything that's a hard gap on equipment or expertise is a plausible
    # collaboration candidate.
    closable_via_collaboration = missing_equipment + expertise_gaps

    return GapAnalysis(
        opportunity_id=opp.id,
        missing_equipment=missing_equipment,
        acquirable_equipment=acquirable_equipment,
        skill_gaps=skill_gaps,
        learnable_skills=learnable_skills,
        expertise_gaps=expertise_gaps,
        estimated_effort=_estimate_effort(breakdown),
        closable_via_collaboration=closable_via_collaboration,
    )
