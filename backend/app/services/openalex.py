"""OpenAlex API client.

Replaces the previous ORCID-Public-API + PubMed two-phase fetch with a
single endpoint: OpenAlex resolves an ORCID directly to works (title,
abstract, DOI, year, authors, concepts) in one filter call. Unlike PubMed,
OpenAlex covers all disciplines — biomed, chemistry, physics, materials,
CS, ecology, humanities — which is the reason for the swap.

Public API, no key. We send a `mailto:` in the User-Agent to land in the
polite pool (100k req/day, low-latency tier).
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Any

import httpx

OPENALEX_BASE_URL = "https://api.openalex.org"

# 16 digits in 4-4-4-4 groups; final character is a Mod-11 checksum digit
# that may be 0–9 or 'X' (representing 10).
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

# Fields we ask OpenAlex to return — keeps payloads small even for prolific
# authors. `abstract_inverted_index` is OpenAlex's compact abstract format
# (see _reconstruct_abstract).
_WORK_FIELDS = ",".join(
    [
        "id",
        "doi",
        "title",
        "abstract_inverted_index",
        "authorships",
        "publication_year",
        "publication_date",
        "primary_location",
        "concepts",
    ]
)


def is_valid_orcid(orcid_id: str) -> bool:
    return bool(_ORCID_RE.match(orcid_id))


class OpenAlexError(Exception):
    """Raised when the OpenAlex API returns an unrecoverable error."""


class OpenAlexClient:
    """Client for the OpenAlex `/works` endpoint."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        contact_email: str | None = None,
    ) -> None:
        self._client = http_client
        # Polite pool gets ~10 req/sec headroom; cap below to leave slack.
        self._semaphore = asyncio.Semaphore(8)
        self._headers = {
            "Accept": "application/json",
            "User-Agent": (
                f"phosphor (mailto:{contact_email})"
                if contact_email
                else "phosphor"
            ),
        }

    async def fetch_works_by_orcid(
        self,
        orcid_id: str,
        max_results: int = 200,
    ) -> list[dict[str, Any]]:
        """Fetch publications for an ORCID iD.

        Returns normalized paper dicts with the same shape the downstream
        capability-extraction pipeline expects:
            ``{"doi", "pmid", "title", "abstract", "authors", "journal",
               "publication_date", "mesh_terms", "source"}``

        ``pmid`` is always None (OpenAlex doesn't surface it as a primary id),
        and ``mesh_terms`` is populated from OpenAlex Concepts so the
        extraction prompt still has topic hints.

        Papers without abstracts are dropped — capability extraction needs
        the body text.

        Raises:
            OpenAlexError: invalid ORCID format or non-recoverable HTTP error.
        """
        if not is_valid_orcid(orcid_id):
            raise OpenAlexError(f"Invalid ORCID iD format: {orcid_id}")

        params: dict[str, str] = {
            "filter": f"author.orcid:{orcid_id}",
            "per-page": str(min(max_results, 200)),
            "select": _WORK_FIELDS,
            "sort": "publication_year:desc",
        }

        async with self._semaphore:
            response = await self._client.get(
                f"{OPENALEX_BASE_URL}/works",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )

        if response.status_code == 404:
            raise OpenAlexError(f"ORCID iD not found in OpenAlex: {orcid_id}")
        if response.status_code != 200:
            raise OpenAlexError(
                f"OpenAlex API error: HTTP {response.status_code} for {orcid_id}"
            )

        data = response.json()
        return self._parse_works(data.get("results") or [])

    async def search(
        self,
        query: str,
        field_of_study: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Free-text search across all of OpenAlex.

        Used by the literature-scan path. ``field_of_study`` is matched
        against OpenAlex Concepts via the `concepts.display_name.search`
        filter.
        """
        params: dict[str, str] = {
            "search": query,
            "per-page": str(min(max_results, 200)),
            "select": _WORK_FIELDS,
        }
        if field_of_study:
            params["filter"] = f"concepts.display_name.search:{field_of_study}"

        async with self._semaphore:
            response = await self._client.get(
                f"{OPENALEX_BASE_URL}/works",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )

        if response.status_code != 200:
            raise OpenAlexError(
                f"OpenAlex search error: HTTP {response.status_code}"
            )

        data = response.json()
        return self._parse_works(data.get("results") or [])

    @classmethod
    def _parse_works(cls, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        papers: list[dict[str, Any]] = []
        for work in results:
            paper = cls._parse_work(work)
            if paper is not None:
                papers.append(paper)
        return papers

    @classmethod
    def _parse_work(cls, work: dict[str, Any]) -> dict[str, Any] | None:
        title = work.get("title") or ""
        if not title.strip():
            return None

        abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
        if not abstract:
            # Same policy as the old PubMed path: skip works without abstracts
            # because capability extraction has nothing to read.
            return None

        return {
            "pmid": None,
            "doi": _strip_doi(work.get("doi")),
            "title": title.strip(),
            "abstract": abstract,
            "authors": _extract_authors(work.get("authorships") or []),
            "journal": _extract_journal(work.get("primary_location")),
            "publication_date": _extract_publication_date(work),
            "mesh_terms": _extract_concept_names(work.get("concepts") or []),
            "source": "openalex",
        }


def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Invert OpenAlex's abstract_inverted_index back to plain text.

    OpenAlex stores abstracts as ``{word: [positions...]}`` (a copyright
    workaround — the original ordering is recoverable but the format isn't
    obviously a "copy"). We rebuild the linear sentence by sorting positions.
    """
    if not inverted:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        for pos in positions:
            positioned.append((pos, word))
    positioned.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positioned)


def _strip_doi(doi: str | None) -> str | None:
    """OpenAlex returns DOIs as full URLs (``https://doi.org/10.x/y``).

    Downstream code (paper dedup, capability sources) expects the bare DOI.
    """
    if not doi:
        return None
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix) :]
    return doi


def _extract_authors(authorships: list[dict[str, Any]]) -> list[dict[str, str]]:
    authors: list[dict[str, str]] = []
    for entry in authorships:
        author = entry.get("author") or {}
        display_name = (author.get("display_name") or "").strip()
        if not display_name:
            continue
        # Best-effort split on the last whitespace — OpenAlex doesn't give us
        # structured first/last name, but downstream consumers only need
        # something to display.
        parts = display_name.rsplit(" ", 1)
        if len(parts) == 2:
            first, last = parts
        else:
            first, last = "", display_name
        authors.append({"first_name": first, "last_name": last})
    return authors


def _extract_journal(primary_location: dict[str, Any] | None) -> str | None:
    if not primary_location:
        return None
    source = primary_location.get("source") or {}
    name = source.get("display_name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _extract_publication_date(work: dict[str, Any]) -> date | None:
    raw = work.get("publication_date")
    if isinstance(raw, str) and raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    year = work.get("publication_year")
    if isinstance(year, int):
        try:
            return date(year, 1, 1)
        except ValueError:
            return None
    return None


def _extract_concept_names(concepts: list[dict[str, Any]]) -> list[str]:
    """Take the highest-scoring OpenAlex Concepts as topic hints.

    These play the role MeSH terms played in the previous pipeline: a short
    controlled-vocabulary list passed to the extraction prompt as context.
    Cap at 10 so the user prompt doesn't bloat.
    """
    names: list[str] = []
    for c in concepts[:10]:
        name = c.get("display_name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


__all__ = [
    "OPENALEX_BASE_URL",
    "OpenAlexClient",
    "OpenAlexError",
    "is_valid_orcid",
]
