"""LLM-driven capability extraction from a researcher's publications.

Distinct from `app/services/extraction.py`, which extracts research
*opportunities* from literature for matching. This service extracts the
lab's *current capabilities* — techniques, organisms, equipment, reagents,
expertise — from papers the lab has authored. Output feeds the ORCID
import flow and is reviewed by the user before commit.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import Callable
from typing import Any, Literal

from litellm import acompletion
from pydantic import BaseModel, ConfigDict, Field

from app.agents.prompts import load_prompt
from app.core.config import Settings, get_settings
from app.schemas.lab_state_import import (
    CapabilitySource,
    ProposedEquipment,
    ProposedExpertise,
    ProposedLabState,
    ProposedOrganism,
    ProposedReagent,
    ProposedTechnique,
)

EXTRACTION_PROMPT_VERSION = "capability-v1"

# Common-abbreviation alias map. Lowercased canonical normalization happens
# first; this map collapses well-known synonyms onto a single canonical form
# so the same capability extracted across papers aggregates instead of
# fragmenting. Conservative on purpose — we'd rather under-merge than
# silently combine distinct techniques.
_TECHNIQUE_ALIASES: dict[str, str] = {
    "qpcr": "quantitative pcr",
    "rt-qpcr": "quantitative pcr",
    "rt-pcr": "reverse transcription pcr",
    "wb": "western blot",
    "ihc": "immunohistochemistry",
    "if": "immunofluorescence",
    "ko": "knockout",
    "ki": "knock-in",
    "scrna-seq": "single-cell rna-seq",
    "scrnaseq": "single-cell rna-seq",
    "single cell rna-seq": "single-cell rna-seq",
    "single-cell rna sequencing": "single-cell rna-seq",
    "atac-seq": "atac-seq",
    "chip-seq": "chip-seq",
    "chip seq": "chip-seq",
    "rna-seq": "rna-seq",
    "rna seq": "rna-seq",
    "lc-ms/ms": "lc-ms/ms",
    "lc/ms": "lc-ms",
    "ms/ms": "tandem mass spectrometry",
    "fish": "fluorescence in situ hybridization",
    "facs": "fluorescence-activated cell sorting",
    "em": "electron microscopy",
    "cryo-em": "cryo-electron microscopy",
    "cryoem": "cryo-electron microscopy",
    "smfret": "single-molecule fret",
}

# Canonical organism aliases — common cell lines and model organisms.
_ORGANISM_ALIASES: dict[str, str] = {
    "mouse": "mus musculus",
    "mice": "mus musculus",
    "murine": "mus musculus",
    "rat": "rattus norvegicus",
    "yeast": "saccharomyces cerevisiae",
    "s. cerevisiae": "saccharomyces cerevisiae",
    "e. coli": "escherichia coli",
    "drosophila": "drosophila melanogaster",
    "fruit fly": "drosophila melanogaster",
    "fly": "drosophila melanogaster",
    "zebrafish": "danio rerio",
    "c. elegans": "caenorhabditis elegans",
    "worm": "caenorhabditis elegans",
    "human": "homo sapiens",
}

_WS_RE = re.compile(r"\s+")


def _normalize_name(name: str, aliases: dict[str, str] | None = None) -> str:
    """Lowercase, collapse whitespace, strip punctuation runs, then alias-map."""
    norm = _WS_RE.sub(" ", name.strip().lower()).strip(" .,;:")
    if aliases and norm in aliases:
        return aliases[norm]
    return norm


class _ExtractedItem(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    name: str = Field(..., min_length=1, max_length=200)
    evidence: str = Field(default="", max_length=400)


class _ExtractedExpertise(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    domain: str = Field(..., min_length=1, max_length=200)
    evidence: str = Field(default="", max_length=400)


class CapabilityExtraction(BaseModel):
    """Per-paper LLM extraction output, validated."""

    model_config = ConfigDict(strict=True, extra="ignore")

    techniques: list[_ExtractedItem] = Field(default_factory=list)
    organisms: list[_ExtractedItem] = Field(default_factory=list)
    equipment: list[_ExtractedItem] = Field(default_factory=list)
    reagents: list[_ExtractedItem] = Field(default_factory=list)
    expertise: list[_ExtractedExpertise] = Field(default_factory=list)


async def extract_capabilities_from_paper(
    paper: dict[str, Any],
    settings: Settings | None = None,
) -> CapabilityExtraction:
    """Run LLM extraction over a single paper. Returns an empty result on parse failure."""
    if settings is None:
        settings = get_settings()

    system_prompt = load_prompt("capability_extraction")

    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    mesh = paper.get("mesh_terms") or []
    year = paper.get("publication_date")
    year_str = ""
    if year is not None:
        year_str = str(getattr(year, "year", year))

    user_prompt = (
        f"Title: {title}\n"
        f"Year: {year_str or 'unknown'}\n"
        f"MeSH terms: {', '.join(mesh) if mesh else 'none'}\n\n"
        f"Abstract:\n{abstract}\n\n"
        "Output the JSON object now:"
    )

    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=2000,
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return CapabilityExtraction()

    if not isinstance(raw, dict):
        return CapabilityExtraction()

    try:
        return CapabilityExtraction.model_validate(raw)
    except Exception:  # noqa: BLE001 — bad LLM output is non-fatal per paper
        return CapabilityExtraction()


async def extract_capabilities_batch(
    papers: list[dict[str, Any]],
    concurrency: int = 5,
    on_paper_done: Callable[[int], None] | None = None,
    settings: Settings | None = None,
) -> list[CapabilityExtraction]:
    """Extract capabilities for many papers concurrently.

    `on_paper_done` is invoked after each paper completes so callers (the
    Celery task) can persist a `progress.papers_processed` bump.
    """
    if settings is None:
        settings = get_settings()

    sem = asyncio.Semaphore(concurrency)
    counter = {"done": 0}
    counter_lock = asyncio.Lock()

    async def _one(paper: dict[str, Any]) -> CapabilityExtraction:
        async with sem:
            try:
                result = await extract_capabilities_from_paper(paper, settings)
            except Exception:  # noqa: BLE001 — never let one paper kill the batch
                result = CapabilityExtraction()
        if on_paper_done is not None:
            async with counter_lock:
                counter["done"] += 1
                done = counter["done"]
            # Progress hook errors are non-fatal — never block extraction.
            with contextlib.suppress(Exception):
                on_paper_done(done)
        return result

    return await asyncio.gather(*(_one(p) for p in papers))


def aggregate_capabilities(
    extractions: list[CapabilityExtraction],
    papers: list[dict[str, Any]],
) -> ProposedLabState:
    """Aggregate per-paper extractions into a deduped, provenance-tagged state.

    Precondition: ``len(extractions) == len(papers)`` and indices are aligned.
    """
    if len(extractions) != len(papers):
        raise ValueError("extractions and papers must be the same length")

    techniques: dict[str, _Bucket] = {}
    organisms: dict[str, _Bucket] = {}
    equipment: dict[str, _Bucket] = {}
    reagents: dict[str, _Bucket] = {}
    expertise: dict[str, _Bucket] = {}

    for extraction, paper in zip(extractions, papers, strict=True):
        source = _make_source(paper)

        for item in extraction.techniques:
            _accumulate(techniques, _normalize_name(item.name, _TECHNIQUE_ALIASES), item.name, source)
        for item in extraction.organisms:
            _accumulate(organisms, _normalize_name(item.name, _ORGANISM_ALIASES), item.name, source)
        for item in extraction.equipment:
            _accumulate(equipment, _normalize_name(item.name), item.name, source)
        for item in extraction.reagents:
            _accumulate(reagents, _normalize_name(item.name), item.name, source)
        for ex in extraction.expertise:
            _accumulate(expertise, _normalize_name(ex.domain), ex.domain, source)

    return ProposedLabState(
        techniques=[
            ProposedTechnique(
                name=b.display_name,
                proficiency=_default_proficiency(b.frequency),
                notes=None,
                sources=b.sources,
                frequency=b.frequency,
            )
            for b in _sorted_buckets(techniques)
        ],
        organisms=[
            ProposedOrganism(
                name=b.display_name,
                strains=[],
                notes=None,
                sources=b.sources,
                frequency=b.frequency,
            )
            for b in _sorted_buckets(organisms)
        ],
        equipment=[
            ProposedEquipment(
                name=b.display_name,
                capabilities=[],
                limitations=None,
                sources=b.sources,
                frequency=b.frequency,
            )
            for b in _sorted_buckets(equipment)
        ],
        reagents=[
            ProposedReagent(
                name=b.display_name,
                quantity=None,
                notes=None,
                sources=b.sources,
                frequency=b.frequency,
            )
            for b in _sorted_buckets(reagents)
        ],
        expertise=[
            ProposedExpertise(
                domain=b.display_name,
                confidence=_default_confidence(b.frequency),
                sources=b.sources,
                frequency=b.frequency,
            )
            for b in _sorted_buckets(expertise)
        ],
    )


class _Bucket:
    """Mutable accumulator used internally during aggregation."""

    __slots__ = ("display_name", "frequency", "sources", "_seen_pmids")

    def __init__(self, display_name: str) -> None:
        self.display_name = display_name
        self.frequency = 0
        self.sources: list[CapabilitySource] = []
        self._seen_pmids: set[str] = set()

    def add(self, source: CapabilitySource) -> None:
        # Dedupe by PMID (or DOI when no PMID) so the same paper contributing
        # the technique twice doesn't double-count.
        key = source.pmid or source.doi or source.title
        if key in self._seen_pmids:
            return
        self._seen_pmids.add(key)
        self.frequency += 1
        self.sources.append(source)


def _accumulate(
    buckets: dict[str, _Bucket],
    canonical: str,
    raw_name: str,
    source: CapabilitySource,
) -> None:
    if not canonical:
        return
    bucket = buckets.get(canonical)
    if bucket is None:
        bucket = _Bucket(_pretty_display(raw_name, canonical))
        buckets[canonical] = bucket
    bucket.add(source)


def _pretty_display(raw: str, canonical: str) -> str:
    """Pick a user-facing display string.

    If the canonical form is an alias-mapped target, use it (it's the
    well-known full name, e.g. "single-cell rna-seq"). Otherwise fall back to
    the original raw name so casing like "CRISPR-Cas9" is preserved.
    """
    if _WS_RE.sub(" ", raw.strip().lower()).strip(" .,;:") == canonical:
        return raw.strip()
    # Canonical came from an alias map — capitalize sensibly.
    return canonical


def _sorted_buckets(buckets: dict[str, _Bucket]) -> list[_Bucket]:
    return sorted(buckets.values(), key=lambda b: (-b.frequency, b.display_name))


def _make_source(paper: dict[str, Any]) -> CapabilitySource:
    pub_date = paper.get("publication_date")
    year: int | None = None
    if pub_date is not None:
        year = getattr(pub_date, "year", None) or (
            int(pub_date) if isinstance(pub_date, int) else None
        )
    return CapabilitySource(
        pmid=paper.get("pmid"),
        doi=paper.get("doi"),
        title=paper.get("title", "(untitled)"),
        year=year,
    )


def _default_proficiency(frequency: int) -> Literal["expert", "competent", "learning"]:
    # Frequency in the publication record maps to coarse proficiency:
    # one-off paper → learning, a few → competent, many → expert.
    if frequency >= 5:
        return "expert"
    if frequency >= 2:
        return "competent"
    return "learning"


def _default_confidence(frequency: int) -> Literal["high", "medium", "low"]:
    if frequency >= 5:
        return "high"
    if frequency >= 2:
        return "medium"
    return "low"
