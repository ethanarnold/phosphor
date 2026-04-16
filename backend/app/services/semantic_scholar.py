"""Semantic Scholar API client."""

import asyncio
import contextlib
from datetime import date
from typing import Any

import httpx

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "paperId,externalIds,title,abstract,authors,journal,year,fieldsOfStudy"


class SemanticScholarClient:
    """Client for the Semantic Scholar Academic Graph API."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str | None = None,
    ) -> None:
        self._client = http_client
        self._api_key = api_key
        # S2: 100 requests per 5 minutes without key
        self._semaphore = asyncio.Semaphore(5)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def search(
        self,
        query: str,
        field_of_study: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for papers by query.

        Args:
            query: Free-text search query
            field_of_study: Optional field filter (e.g. "Biology", "Chemistry")
            max_results: Maximum papers to return

        Returns:
            List of normalized paper dicts
        """
        results: list[dict[str, Any]] = []
        offset = 0
        limit = min(max_results, 100)  # S2 max per request

        while len(results) < max_results:
            params: dict[str, Any] = {
                "query": query,
                "fields": S2_FIELDS,
                "offset": offset,
                "limit": limit,
            }
            if field_of_study:
                params["fieldsOfStudy"] = field_of_study

            async with self._semaphore:
                response = await self._client.get(
                    f"{S2_BASE_URL}/paper/search",
                    params=params,
                    headers=self._headers(),
                    timeout=30.0,
                )
                response.raise_for_status()

            data = response.json()
            papers = data.get("data", [])
            if not papers:
                break

            for paper in papers:
                normalized = self._normalize_paper(paper)
                if normalized:
                    results.append(normalized)

            offset += len(papers)
            if offset >= data.get("total", 0):
                break

            # Brief delay between paginated requests
            await asyncio.sleep(0.5)

        return results[:max_results]

    async def get_citations(
        self,
        paper_id: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Get papers that cite the given paper.

        Args:
            paper_id: Semantic Scholar paper ID
            max_results: Maximum citing papers to return

        Returns:
            List of normalized paper dicts
        """
        params = {
            "fields": S2_FIELDS,
            "limit": min(max_results, 100),
        }

        async with self._semaphore:
            response = await self._client.get(
                f"{S2_BASE_URL}/paper/{paper_id}/citations",
                params=params,
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()

        data = response.json()
        results: list[dict[str, Any]] = []
        for citation in data.get("data", []):
            citing_paper = citation.get("citingPaper", {})
            normalized = self._normalize_paper(citing_paper)
            if normalized:
                results.append(normalized)

        return results

    def _normalize_paper(self, paper: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize a Semantic Scholar paper to our standard format."""
        title = paper.get("title")
        abstract = paper.get("abstract")

        if not title or not abstract:
            return None  # Skip papers without title or abstract

        # Extract external IDs
        external_ids = paper.get("externalIds") or {}
        doi = external_ids.get("DOI")
        pmid = external_ids.get("PubMed")

        # Authors
        authors: list[dict[str, str]] = []
        for author in paper.get("authors", []) or []:
            name = author.get("name", "")
            parts = name.rsplit(" ", 1)
            if len(parts) == 2:
                authors.append({"first_name": parts[0], "last_name": parts[1]})
            else:
                authors.append({"last_name": name, "first_name": ""})

        # Journal
        journal_info = paper.get("journal") or {}
        journal = journal_info.get("name")

        # Publication date (S2 only provides year)
        pub_date = None
        year = paper.get("year")
        if year:
            with contextlib.suppress(ValueError, TypeError):
                pub_date = date(int(year), 1, 1)

        return {
            "semantic_scholar_id": paper.get("paperId"),
            "doi": doi,
            "pmid": str(pmid) if pmid else None,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "publication_date": pub_date,
            "mesh_terms": [],  # S2 doesn't provide MeSH terms
            "fields_of_study": paper.get("fieldsOfStudy") or [],
            "source": "semantic_scholar",
        }
