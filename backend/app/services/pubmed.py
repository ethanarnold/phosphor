"""PubMed E-utilities API client."""

import asyncio
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import httpx

PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    """Client for PubMed E-utilities (ESearch + EFetch)."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str | None = None,
    ) -> None:
        self._client = http_client
        self._api_key = api_key
        # PubMed: 3 req/sec without key, 10 req/sec with key
        self._semaphore = asyncio.Semaphore(3 if api_key is None else 10)

    def _base_params(self) -> dict[str, str]:
        params: dict[str, str] = {"retmode": "xml"}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def search(
        self,
        query: str,
        mesh_terms: list[str] | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search PubMed and fetch matching paper metadata.

        Args:
            query: Free-text search query
            mesh_terms: Optional MeSH terms to refine search
            max_results: Maximum papers to return

        Returns:
            List of normalized paper dicts
        """
        # Build search query with optional MeSH terms
        search_parts = [query]
        if mesh_terms:
            for term in mesh_terms:
                search_parts.append(f'"{term}"[MeSH]')
        full_query = " AND ".join(search_parts)

        pmids = await self._esearch(full_query, max_results)
        if not pmids:
            return []

        return await self.fetch_by_pmids(pmids)

    async def _esearch(self, query: str, max_results: int) -> list[str]:
        """Run ESearch to get PMIDs matching a query."""
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "sort": "relevance",
        }

        async with self._semaphore:
            response = await self._client.get(
                f"{PUBMED_BASE_URL}/esearch.fcgi",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()

        root = ET.fromstring(response.text)
        id_list = root.find("IdList")
        if id_list is None:
            return []

        return [id_el.text for id_el in id_list.findall("Id") if id_el.text]

    async def fetch_by_pmids(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Fetch full metadata for a list of PMIDs via EFetch."""
        if not pmids:
            return []

        # Batch in groups of 200 (PubMed limit)
        results: list[dict[str, Any]] = []
        for i in range(0, len(pmids), 200):
            batch = pmids[i : i + 200]
            batch_results = await self._efetch_batch(batch)
            results.extend(batch_results)

        return results

    async def _efetch_batch(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Fetch a batch of papers from EFetch."""
        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
        }

        async with self._semaphore:
            response = await self._client.get(
                f"{PUBMED_BASE_URL}/efetch.fcgi",
                params=params,
                timeout=60.0,
            )
            response.raise_for_status()

        return self._parse_efetch_xml(response.text)

    def _parse_efetch_xml(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse EFetch XML response into normalized paper dicts."""
        root = ET.fromstring(xml_text)
        papers: list[dict[str, Any]] = []

        for article in root.findall(".//PubmedArticle"):
            paper = self._parse_article(article)
            if paper:
                papers.append(paper)

        return papers

    def _parse_article(self, article: ET.Element) -> dict[str, Any] | None:
        """Parse a single PubmedArticle element."""
        medline = article.find("MedlineCitation")
        if medline is None:
            return None

        # PMID
        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else None

        art = medline.find("Article")
        if art is None:
            return None

        # Title
        title_el = art.find("ArticleTitle")
        title = title_el.text if title_el is not None else ""

        # Abstract
        abstract_parts: list[str] = []
        abstract_el = art.find("Abstract")
        if abstract_el is not None:
            for text_el in abstract_el.findall("AbstractText"):
                label = text_el.get("Label", "")
                text_content = "".join(text_el.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text_content}")
                else:
                    abstract_parts.append(text_content)
        abstract = " ".join(abstract_parts)

        if not abstract:
            return None  # Skip papers without abstracts

        # Authors
        authors: list[dict[str, str]] = []
        author_list = art.find("AuthorList")
        if author_list is not None:
            for author_el in author_list.findall("Author"):
                last = author_el.find("LastName")
                first = author_el.find("ForeName")
                if last is not None:
                    authors.append(
                        {
                            "last_name": last.text or "",
                            "first_name": (first.text or "") if first is not None else "",
                        }
                    )

        # Journal
        journal_el = art.find("Journal/Title")
        journal = journal_el.text if journal_el is not None else None

        # Publication date
        pub_date = self._parse_pub_date(art)

        # DOI
        doi = None
        article_ids = article.find("PubmedData/ArticleIdList")
        if article_ids is not None:
            for aid in article_ids.findall("ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text
                    break

        # MeSH terms
        mesh_terms: list[str] = []
        mesh_list = medline.find("MeshHeadingList")
        if mesh_list is not None:
            for heading in mesh_list.findall("MeshHeading"):
                desc = heading.find("DescriptorName")
                if desc is not None and desc.text:
                    mesh_terms.append(desc.text)

        return {
            "pmid": pmid,
            "doi": doi,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "publication_date": pub_date,
            "mesh_terms": mesh_terms,
            "source": "pubmed",
        }

    def _parse_pub_date(self, article: ET.Element) -> date | None:
        """Extract publication date from article."""
        # Try ArticleDate first (electronic pub)
        for date_el in article.findall("ArticleDate"):
            year = date_el.find("Year")
            month = date_el.find("Month")
            day = date_el.find("Day")
            if year is not None and year.text:
                try:
                    return date(
                        int(year.text),
                        int(month.text) if month is not None and month.text else 1,
                        int(day.text) if day is not None and day.text else 1,
                    )
                except (ValueError, TypeError):
                    pass

        # Fall back to Journal PubDate
        pub_date = article.find("Journal/JournalIssue/PubDate")
        if pub_date is not None:
            year = pub_date.find("Year")
            if year is not None and year.text:
                month = pub_date.find("Month")
                try:
                    month_text = month.text if month is not None else None
                    month_num = int(month_text) if month_text and month_text.isdigit() else 1
                    return date(int(year.text), month_num, 1)
                except (ValueError, TypeError):
                    try:
                        return date(int(year.text), 1, 1)
                    except ValueError:
                        pass

        return None
