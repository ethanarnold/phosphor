"""Unit tests for OpenAlexClient parsing.

Network-touching paths (`fetch_works_by_orcid`, `search`) are exercised in
integration tests; here we only check the deterministic parser pieces.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.openalex import (
    OpenAlexClient,
    OpenAlexError,
    _reconstruct_abstract,
    _strip_doi,
    is_valid_orcid,
)


class TestIsValidOrcid:
    def test_accepts_well_formed_id(self) -> None:
        assert is_valid_orcid("0000-0002-1825-0097")

    def test_accepts_x_checksum(self) -> None:
        assert is_valid_orcid("0000-0001-5000-001X")

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "0000-0002-1825-009",  # 15 digits
            "0000-0002-1825-00977",  # 17 digits
            "0000 0002 1825 0097",  # spaces, not dashes
            "0000-0002-1825-009Y",  # bad checksum char
            "https://orcid.org/0000-0002-1825-0097",  # URL form
        ],
    )
    def test_rejects_malformed(self, value: str) -> None:
        assert not is_valid_orcid(value)


class TestStripDoi:
    def test_strips_https_prefix(self) -> None:
        assert _strip_doi("https://doi.org/10.1093/nar/gkaf290") == "10.1093/nar/gkaf290"

    def test_lowercases_doi(self) -> None:
        assert _strip_doi("https://doi.org/10.1093/NAR/GKAF290") == "10.1093/nar/gkaf290"

    def test_passes_through_bare_doi(self) -> None:
        assert _strip_doi("10.1093/nar/gkaf290") == "10.1093/nar/gkaf290"

    def test_none_in_none_out(self) -> None:
        assert _strip_doi(None) is None


class TestReconstructAbstract:
    def test_inverts_index(self) -> None:
        # "the quick brown fox" → positions 0,1,2,3
        inverted = {"the": [0], "quick": [1], "brown": [2], "fox": [3]}
        assert _reconstruct_abstract(inverted) == "the quick brown fox"

    def test_handles_repeated_words(self) -> None:
        # "to be or not to be"
        inverted = {"to": [0, 4], "be": [1, 5], "or": [2], "not": [3]}
        assert _reconstruct_abstract(inverted) == "to be or not to be"

    def test_empty_or_none(self) -> None:
        assert _reconstruct_abstract(None) == ""
        assert _reconstruct_abstract({}) == ""


class TestParseWork:
    def _full_work(self) -> dict:
        return {
            "id": "https://openalex.org/W4409482992",
            "doi": "https://doi.org/10.1093/nar/gkaf290",
            "title": "Investigating the interplay between RNA structural dynamics and probing",
            "abstract_inverted_index": {
                "RNA": [0],
                "chemical": [1],
                "probing": [2],
                "experiments.": [3],
            },
            "publication_year": 2025,
            "publication_date": "2025-04-15",
            "primary_location": {"source": {"display_name": "Nucleic Acids Research"}},
            "authorships": [
                {"author": {"display_name": "Ethan B Arnold"}},
                {"author": {"display_name": "Alisha Jones"}},
            ],
            "concepts": [
                {"display_name": "RNA structure", "score": 0.9},
                {"display_name": "Computational biology", "score": 0.8},
            ],
        }

    def test_full_parse(self) -> None:
        paper = OpenAlexClient._parse_work(self._full_work())
        assert paper is not None
        assert paper["doi"] == "10.1093/nar/gkaf290"
        assert paper["pmid"] is None
        assert paper["title"].startswith("Investigating")
        assert paper["abstract"] == "RNA chemical probing experiments."
        assert paper["journal"] == "Nucleic Acids Research"
        assert paper["publication_date"] == date(2025, 4, 15)
        assert paper["mesh_terms"] == ["RNA structure", "Computational biology"]
        assert paper["source"] == "openalex"
        assert {a["last_name"] for a in paper["authors"]} == {"Arnold", "Jones"}

    def test_skip_when_no_abstract(self) -> None:
        work = self._full_work()
        work["abstract_inverted_index"] = None
        assert OpenAlexClient._parse_work(work) is None

    def test_skip_when_no_title(self) -> None:
        work = self._full_work()
        work["title"] = ""
        assert OpenAlexClient._parse_work(work) is None

    def test_falls_back_to_year_only_date(self) -> None:
        work = self._full_work()
        del work["publication_date"]
        paper = OpenAlexClient._parse_work(work)
        assert paper is not None
        assert paper["publication_date"] == date(2025, 1, 1)


class TestFetchWorksValidation:
    @pytest.mark.asyncio
    async def test_invalid_orcid_raises_before_request(self) -> None:
        # http_client is unused — error should fire on validation, not network.
        client = OpenAlexClient(http_client=None)  # type: ignore[arg-type]
        with pytest.raises(OpenAlexError, match="Invalid ORCID"):
            await client.fetch_works_by_orcid("not-an-orcid")
