"""Unit tests for the publication-import capability extractor.

Tests in this file are pure-Python — they cover canonical-name normalization,
the alias map, and per-paper provenance accumulation. Precision/recall over
real LLM output lives under `/evals/extraction/test_capability_extraction.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.services.capability_extraction import (
    CapabilityExtraction,
    aggregate_capabilities,
)


def _make_paper(idx: int, year: int = 2023) -> dict[str, Any]:
    return {
        "pmid": f"100{idx:04d}",
        "doi": f"10.1/p{idx}",
        "title": f"Paper {idx}",
        "abstract": "...",
        "mesh_terms": [],
        "publication_date": date(year, 1, 1),
    }


def _make_extraction(**kwargs: Any) -> CapabilityExtraction:
    """Build a CapabilityExtraction from kwargs, filling in empty arrays."""
    payload: dict[str, list[dict[str, str]]] = {
        "techniques": [],
        "organisms": [],
        "equipment": [],
        "reagents": [],
        "expertise": [],
    }
    payload.update(kwargs)
    return CapabilityExtraction.model_validate(payload)


class TestAggregation:
    def test_dedupes_by_paper_with_casing_variants(self) -> None:
        papers = [_make_paper(i) for i in range(5)]
        extractions = [
            _make_extraction(techniques=[{"name": variant, "evidence": "x"}])
            for variant in [
                "Western Blot",
                "western blot",
                "Western  blot",  # whitespace collapse
                "western blot.",  # trailing punctuation
                "Western blot",
            ]
        ]
        proposed = aggregate_capabilities(extractions, papers)
        assert len(proposed.techniques) == 1
        assert proposed.techniques[0].frequency == 5
        assert len(proposed.techniques[0].sources) == 5

    def test_alias_map_collapses_qpcr_synonyms(self) -> None:
        papers = [_make_paper(0), _make_paper(1)]
        extractions = [
            _make_extraction(techniques=[{"name": "qPCR", "evidence": "x"}]),
            _make_extraction(techniques=[{"name": "quantitative PCR", "evidence": "y"}]),
        ]
        proposed = aggregate_capabilities(extractions, papers)
        assert len(proposed.techniques) == 1
        assert proposed.techniques[0].frequency == 2

    def test_organism_aliases_mouse_to_mus_musculus(self) -> None:
        papers = [_make_paper(0), _make_paper(1)]
        extractions = [
            _make_extraction(organisms=[{"name": "mouse", "evidence": "x"}]),
            _make_extraction(organisms=[{"name": "Mus musculus", "evidence": "y"}]),
        ]
        proposed = aggregate_capabilities(extractions, papers)
        assert len(proposed.organisms) == 1
        assert proposed.organisms[0].frequency == 2

    def test_distinct_techniques_stay_separate(self) -> None:
        papers = [_make_paper(0)]
        extractions = [
            _make_extraction(
                techniques=[
                    {"name": "Western blot", "evidence": "x"},
                    {"name": "Northern blot", "evidence": "y"},
                ]
            )
        ]
        proposed = aggregate_capabilities(extractions, papers)
        names = {t.name.lower() for t in proposed.techniques}
        assert "western blot" in names
        assert "northern blot" in names

    def test_sources_carry_pmid_year_title(self) -> None:
        papers = [_make_paper(42, year=2022)]
        extractions = [_make_extraction(techniques=[{"name": "CRISPR-Cas9", "evidence": "x"}])]
        proposed = aggregate_capabilities(extractions, papers)
        assert len(proposed.techniques) == 1
        src = proposed.techniques[0].sources[0]
        assert src.pmid == "1000042"
        assert src.year == 2022
        assert src.title == "Paper 42"

    def test_proficiency_scales_with_frequency(self) -> None:
        # 1 paper → learning, 2-4 → competent, 5+ → expert
        papers = [_make_paper(i) for i in range(6)]
        extractions = [
            _make_extraction(techniques=[{"name": "PCR", "evidence": "x"}])
            for _ in range(6)
        ]
        proposed = aggregate_capabilities(extractions, papers)
        assert proposed.techniques[0].frequency == 6
        assert proposed.techniques[0].proficiency == "expert"

        papers_one = [_make_paper(0)]
        extractions_one = [
            _make_extraction(techniques=[{"name": "PCR", "evidence": "x"}])
        ]
        proposed_one = aggregate_capabilities(extractions_one, papers_one)
        assert proposed_one.techniques[0].proficiency == "learning"

    def test_results_sorted_by_frequency_descending(self) -> None:
        papers = [_make_paper(i) for i in range(3)]
        extractions = [
            _make_extraction(techniques=[
                {"name": "PCR", "evidence": "x"},
                {"name": "Cloning", "evidence": "x"},
            ]),
            _make_extraction(techniques=[{"name": "PCR", "evidence": "x"}]),
            _make_extraction(techniques=[{"name": "PCR", "evidence": "x"}]),
        ]
        proposed = aggregate_capabilities(extractions, papers)
        # PCR appears in 3 papers, Cloning in 1
        assert proposed.techniques[0].name.lower() == "pcr"
        assert proposed.techniques[0].frequency == 3
        assert proposed.techniques[1].name.lower() == "cloning"

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError):
            aggregate_capabilities([], [_make_paper(0)])

    def test_empty_inputs_produce_empty_state(self) -> None:
        proposed = aggregate_capabilities([], [])
        assert proposed.techniques == []
        assert proposed.organisms == []
        assert proposed.equipment == []
        assert proposed.reagents == []
        assert proposed.expertise == []
