"""ORCID Public API client.

Reads public works for a researcher by ORCID iD. No auth needed — the
`pub.orcid.org` host serves public records without OAuth. We only need
DOIs/PMIDs + basic metadata (title, year, journal); abstracts are fetched
downstream from PubMed.
"""

import asyncio
import re
from typing import Any

import httpx

ORCID_BASE_URL = "https://pub.orcid.org/v3.0"

# 16 digits in 4-4-4-4 groups; final character is a Mod-11 checksum digit
# that may be 0–9 or 'X' (representing 10).
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def is_valid_orcid(orcid_id: str) -> bool:
    return bool(_ORCID_RE.match(orcid_id))


class OrcidError(Exception):
    """Raised when the ORCID API returns an unrecoverable error."""


class OrcidClient:
    """Client for the ORCID Public API."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        # Public API allows ~24 req/sec; cap at 8 to leave headroom.
        self._semaphore = asyncio.Semaphore(8)

    async def fetch_works(self, orcid_id: str) -> list[dict[str, Any]]:
        """Fetch the list of public works for the given ORCID iD.

        Returns:
            Normalized list of work dicts:
            ``{"doi": str|None, "pmid": str|None, "title": str, "year": int|None,
               "journal": str|None}``
            with at least one of doi/pmid set (works without external ids are
            dropped — we can't fetch abstracts for them).

        Raises:
            OrcidError: format invalid, profile not found (404), or other
                non-recoverable HTTP error.
        """
        if not is_valid_orcid(orcid_id):
            raise OrcidError(f"Invalid ORCID iD format: {orcid_id}")

        async with self._semaphore:
            response = await self._client.get(
                f"{ORCID_BASE_URL}/{orcid_id}/works",
                headers={"Accept": "application/json"},
                timeout=30.0,
            )

        if response.status_code == 404:
            raise OrcidError(f"ORCID iD not found: {orcid_id}")
        if response.status_code != 200:
            raise OrcidError(
                f"ORCID API error: HTTP {response.status_code} for {orcid_id}"
            )

        data = response.json()
        return self._parse_works(data)

    @staticmethod
    def _parse_works(data: dict[str, Any]) -> list[dict[str, Any]]:
        works: list[dict[str, Any]] = []
        for group in data.get("group", []) or []:
            summaries = group.get("work-summary") or []
            if not summaries:
                continue
            # Use the first summary; ORCID dedupes equivalent records into one
            # group, and the first is typically the user's preferred source.
            summary = summaries[0]

            doi, pmid = _extract_external_ids(group.get("external-ids"))
            if not doi and not pmid:
                # Without an external identifier we can't pull an abstract.
                continue

            title = _extract_title(summary)
            if not title:
                continue

            works.append(
                {
                    "doi": doi,
                    "pmid": pmid,
                    "title": title,
                    "year": _extract_year(summary),
                    "journal": _extract_journal(summary),
                }
            )
        return works


def _extract_external_ids(
    external_ids: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Pull DOI and PMID out of an `external-ids` block."""
    if not external_ids:
        return None, None
    doi: str | None = None
    pmid: str | None = None
    for eid in external_ids.get("external-id", []) or []:
        eid_type = (eid.get("external-id-type") or "").lower()
        eid_value = eid.get("external-id-value") or ""
        if not eid_value:
            continue
        if eid_type == "doi" and doi is None:
            doi = eid_value.strip().lower()
        elif eid_type in ("pmid", "pubmed") and pmid is None:
            pmid = eid_value.strip()
    return doi, pmid


def _extract_title(summary: dict[str, Any]) -> str | None:
    title_block = summary.get("title") or {}
    title_inner = title_block.get("title") or {}
    value = title_inner.get("value")
    return value.strip() if isinstance(value, str) else None


def _extract_year(summary: dict[str, Any]) -> int | None:
    pub_date = summary.get("publication-date") or {}
    year_block = pub_date.get("year") or {}
    value = year_block.get("value")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_journal(summary: dict[str, Any]) -> str | None:
    journal_block = summary.get("journal-title") or {}
    value = journal_block.get("value")
    return value if isinstance(value, str) else None
