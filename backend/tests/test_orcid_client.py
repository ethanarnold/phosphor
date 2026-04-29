"""Unit tests for the ORCID Public API client.

Network-free — exercises iD validation and the `/works` JSON parser. End-to-end
HTTP behaviour is exercised by the import-task integration test (which mocks
the HTTP layer) rather than here.
"""

from __future__ import annotations

import pytest

from app.services.orcid import OrcidClient, OrcidError, is_valid_orcid


class TestOrcidValidation:
    def test_well_formed_iD_accepted(self) -> None:
        assert is_valid_orcid("0000-0002-1825-0097")

    def test_checksum_X_accepted(self) -> None:
        assert is_valid_orcid("0000-0001-5000-001X")

    @pytest.mark.parametrize(
        "value",
        [
            "0000000218250097",  # missing dashes
            "0000-0002-1825-009",  # too short
            "0000-0002-1825-00977",  # too long
            "abcd-0002-1825-0097",  # non-digit
            "",
            "0000-0002-1825-009Y",  # invalid checksum char
        ],
    )
    def test_malformed_iDs_rejected(self, value: str) -> None:
        assert not is_valid_orcid(value)


class TestOrcidWorksParsing:
    SAMPLE_WORKS = {
        "group": [
            # Group 1: paper with both DOI and PMID
            {
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1038/s41586-022-12345-6"},
                        {"external-id-type": "pmid", "external-id-value": "35456789"},
                    ]
                },
                "work-summary": [
                    {
                        "title": {"title": {"value": "A landmark paper on cryo-EM"}},
                        "publication-date": {"year": {"value": "2022"}},
                        "journal-title": {"value": "Nature"},
                    }
                ],
            },
            # Group 2: DOI only
            {
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "DOI", "external-id-value": "10.1126/science.abc1234"},
                    ]
                },
                "work-summary": [
                    {
                        "title": {"title": {"value": "Older study"}},
                        "publication-date": {"year": {"value": "2018"}},
                        "journal-title": {"value": "Science"},
                    }
                ],
            },
            # Group 3: no external IDs — should be dropped
            {
                "external-ids": {"external-id": []},
                "work-summary": [
                    {
                        "title": {"title": {"value": "Untracked work"}},
                        "publication-date": {"year": {"value": "2010"}},
                    }
                ],
            },
            # Group 4: missing title — should be dropped
            {
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "10.1/none"},
                    ]
                },
                "work-summary": [{"title": {"title": {"value": ""}}}],
            },
        ]
    }

    def test_parses_doi_pmid_year_journal(self) -> None:
        works = OrcidClient._parse_works(self.SAMPLE_WORKS)
        assert len(works) == 2

        first = works[0]
        assert first["doi"] == "10.1038/s41586-022-12345-6"
        assert first["pmid"] == "35456789"
        assert first["title"] == "A landmark paper on cryo-EM"
        assert first["year"] == 2022
        assert first["journal"] == "Nature"

    def test_drops_works_without_external_id_or_title(self) -> None:
        works = OrcidClient._parse_works(self.SAMPLE_WORKS)
        titles = [w["title"] for w in works]
        assert "Untracked work" not in titles
        # Group 4 has empty title — should also be dropped
        assert all(w["title"] for w in works)

    def test_doi_lowercased(self) -> None:
        # The 'DOI' uppercase external-id-type still matches; values are also
        # normalized to lowercase since DOIs are case-insensitive.
        works = OrcidClient._parse_works(self.SAMPLE_WORKS)
        second = next(w for w in works if w["title"] == "Older study")
        assert second["doi"] == "10.1126/science.abc1234"

    def test_empty_payload_returns_empty(self) -> None:
        assert OrcidClient._parse_works({}) == []
        assert OrcidClient._parse_works({"group": []}) == []


class TestOrcidFetchValidation:
    @pytest.mark.asyncio
    async def test_fetch_with_invalid_iD_raises_before_http(self) -> None:
        client = OrcidClient(http_client=None)  # type: ignore[arg-type]
        with pytest.raises(OrcidError):
            await client.fetch_works("not-a-real-orcid")
