"""Literature ingestion orchestrator."""

import uuid
from typing import Any

import httpx
from litellm import aembedding
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.paper import Paper
from app.services.pubmed import PubMedClient
from app.services.semantic_scholar import SemanticScholarClient


async def ingest_literature(
    session: AsyncSession,
    lab_id: uuid.UUID,
    query_terms: list[str],
    mesh_terms: list[str] | None = None,
    field_of_study: str | None = None,
    max_results: int = 100,
    sources: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Fetch papers from literature APIs, deduplicate, and store.

    Returns:
        Dict with papers_found and papers_new counts
    """
    if settings is None:
        settings = get_settings()
    if sources is None:
        sources = ["pubmed", "semantic_scholar"]

    query = " ".join(query_terms)
    all_papers: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as http_client:
        # Fetch from PubMed
        if "pubmed" in sources:
            pubmed = PubMedClient(http_client, api_key=settings.pubmed_api_key)
            pubmed_papers = await pubmed.search(
                query=query,
                mesh_terms=mesh_terms,
                max_results=max_results,
            )
            all_papers.extend(pubmed_papers)

        # Fetch from Semantic Scholar
        if "semantic_scholar" in sources:
            s2 = SemanticScholarClient(
                http_client, api_key=settings.semantic_scholar_api_key
            )
            s2_papers = await s2.search(
                query=query,
                field_of_study=field_of_study,
                max_results=max_results,
            )
            all_papers.extend(s2_papers)

    papers_found = len(all_papers)

    # Deduplicate against existing papers in this lab
    new_papers = await deduplicate_papers(session, lab_id, all_papers)

    # Store new papers
    stored = await store_papers(session, lab_id, new_papers)

    return {
        "papers_found": papers_found,
        "papers_new": len(stored),
    }


async def deduplicate_papers(
    session: AsyncSession,
    lab_id: uuid.UUID,
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter out papers that already exist in the lab by DOI or PMID."""
    if not papers:
        return []

    # Collect all DOIs and PMIDs from incoming papers
    incoming_dois = {p["doi"] for p in papers if p.get("doi")}
    incoming_pmids = {p["pmid"] for p in papers if p.get("pmid")}

    existing_dois: set[str] = set()
    existing_pmids: set[str] = set()

    if incoming_dois:
        result = await session.execute(
            select(Paper.doi).where(
                Paper.lab_id == lab_id,
                Paper.doi.in_(incoming_dois),
            )
        )
        existing_dois = {row[0] for row in result.all() if row[0]}

    if incoming_pmids:
        result = await session.execute(
            select(Paper.pmid).where(
                Paper.lab_id == lab_id,
                Paper.pmid.in_(incoming_pmids),
            )
        )
        existing_pmids = {row[0] for row in result.all() if row[0]}

    # Filter: keep papers where neither DOI nor PMID already exists
    seen: set[str] = set()  # Track within batch too
    new_papers: list[dict[str, Any]] = []

    for paper in papers:
        doi = paper.get("doi")
        pmid = paper.get("pmid")

        # Skip if already in DB
        if doi and doi in existing_dois:
            continue
        if pmid and pmid in existing_pmids:
            continue

        # Skip if duplicate within this batch
        dedup_key = doi or pmid or paper.get("title", "")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        new_papers.append(paper)

    return new_papers


async def store_papers(
    session: AsyncSession,
    lab_id: uuid.UUID,
    papers: list[dict[str, Any]],
) -> list[Paper]:
    """Bulk-insert papers into the database."""
    stored: list[Paper] = []

    for paper_data in papers:
        paper = Paper(
            lab_id=lab_id,
            doi=paper_data.get("doi"),
            pmid=paper_data.get("pmid"),
            semantic_scholar_id=paper_data.get("semantic_scholar_id"),
            title=paper_data["title"],
            abstract=paper_data["abstract"],
            authors=paper_data.get("authors"),
            journal=paper_data.get("journal"),
            publication_date=paper_data.get("publication_date"),
            mesh_terms=paper_data.get("mesh_terms"),
            source=paper_data["source"],
            metadata_=paper_data.get("fields_of_study"),
        )
        session.add(paper)
        stored.append(paper)

    await session.flush()
    return stored


async def generate_paper_embeddings(
    session: AsyncSession,
    papers: list[Paper],
    settings: Settings | None = None,
) -> None:
    """Generate and store embeddings for papers using LiteLLM."""
    if settings is None:
        settings = get_settings()

    if not papers:
        return

    texts = [f"{p.title}. {p.abstract}" for p in papers]

    # Batch embedding call
    response = await aembedding(
        model=settings.embedding_model,
        input=texts,
    )

    # Update paper records with embeddings via raw SQL
    # (pgvector columns aren't directly mapped in the ORM)
    from sqlalchemy import text

    for i, paper in enumerate(papers):
        embedding = response.data[i]["embedding"]
        await session.execute(
            text("UPDATE papers SET embedding = :embedding WHERE id = :id"),
            {"embedding": str(embedding), "id": paper.id},
        )

    await session.flush()
