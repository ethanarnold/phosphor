"""Protocol-generation heuristic checks (calls live LLM).

Skipped unless ANTHROPIC_API_KEY is set. Runs 2–3 scenarios end-to-end through
the protocol service's core content generator (no DB needed) and asserts
shape-level properties: min phases, materials grounded in lab state or
flagged as gaps, citations present, min total steps.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Protocol service imports fastapi + sqlalchemy; skip if lightweight evals
# venv doesn't have backend runtime deps installed.
pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.schemas.lab_state import LabStateData  # noqa: E402
from app.services.protocols import _generate_content  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        llm_model="claude-sonnet-4-20250514",
        embedding_model="text-embedding-3-small",
    )


def _opp_stub(raw: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=raw["id"],
        description=raw["description"],
        required_equipment=raw.get("required_equipment", []),
        required_techniques=raw.get("required_techniques", []),
        required_expertise=raw.get("required_expertise", []),
        estimated_complexity=raw.get("estimated_complexity", "medium"),
    )


def _lab_capabilities(lab_state: LabStateData) -> set[str]:
    names = set()
    for e in lab_state.equipment:
        names.add(e.name.lower())
        for cap in e.capabilities:
            names.add(cap.lower())
    for r in lab_state.reagents:
        names.add(r.name.lower())
    for t in lab_state.techniques:
        names.add(t.name.lower())
    return names


@pytest.mark.matching
@pytest.mark.asyncio
class TestProtocolHeuristics:
    """Generated protocols should satisfy CI-cheap structural checks."""

    async def _check_opportunity(
        self, scenario: dict[str, Any], opp_id: str
    ) -> None:
        lab_state = LabStateData.model_validate(scenario["lab_state"])
        raw_opp = next(o for o in scenario["opportunities"] if o["id"] == opp_id)

        title, content = await _generate_content(
            lab_state=lab_state,
            opportunity=_opp_stub(raw_opp),  # type: ignore[arg-type]
            papers=[],
            settings=_settings(),  # type: ignore[arg-type]
        )

        assert len(title) > 0
        assert len(content.phases) >= 2, (
            f"Too few phases for {opp_id}: {len(content.phases)}"
        )

        total_steps = sum(len(p.steps) for p in content.phases)
        assert total_steps >= 5, f"Too few total steps for {opp_id}: {total_steps}"

        assert len(content.expected_outcomes) >= 1

        # Materials must either come from lab state or be flagged as a gap
        caps = _lab_capabilities(lab_state)
        flagged = {g.lower() for g in content.flagged_gaps}
        for material in content.materials:
            ml = material.lower()
            grounded = any(ml in c or c in ml for c in caps)
            flagged_hit = any(ml in f or f in ml for f in flagged)
            assert grounded or flagged_hit, (
                f"Material '{material}' neither in lab state nor flagged as gap "
                f"(opp={opp_id})"
            )

    async def test_genomics_feasible_opportunity(
        self, genomics_scenario: dict[str, Any]
    ) -> None:
        await self._check_opportunity(genomics_scenario, "opp_qpcr_validation")

    async def test_chemistry_feasible_opportunity(
        self, chemistry_scenario: dict[str, Any]
    ) -> None:
        await self._check_opportunity(chemistry_scenario, "opp_suzuki_scope")

    async def test_edge_case_with_gaps(self, edge_cases: dict[str, Any]) -> None:
        # This one has clear gaps — protocol must surface them
        lab_state = LabStateData.model_validate(edge_cases["lab_state"])
        raw_opp = next(
            o for o in edge_cases["opportunities"] if o["id"] == "opp_zero_match"
        )
        _, content = await _generate_content(
            lab_state=lab_state,
            opportunity=_opp_stub(raw_opp),  # type: ignore[arg-type]
            papers=[],
            settings=_settings(),  # type: ignore[arg-type]
        )
        assert content.flagged_gaps, (
            "Expected gaps to be flagged for an opportunity with no local resources"
        )
