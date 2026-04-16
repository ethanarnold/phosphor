"""Opportunity extraction from literature using LLM."""

import contextlib
import json
import uuid
from typing import Any

from litellm import acompletion, aembedding
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.opportunity import Opportunity
from app.models.paper import Paper

EXTRACTION_PROMPT_VERSION = "v1.0.0"

EXTRACTION_SYSTEM_PROMPT = """You are a research opportunity extractor. Given scientific paper abstracts, identify concrete, actionable research opportunities.

Rules:
1. EXTRACT only concrete opportunities with identifiable resource requirements
2. REJECT vague statements like "more research is needed" or "future work should explore"
3. Each opportunity MUST specify at least one of: required_equipment, required_techniques, or required_expertise
4. Rate estimated_complexity based on resource requirements and novelty
5. Rate concreteness_score from 0.0 to 1.0 (how actionable and specific the opportunity is)
6. If NO concrete opportunities exist in the abstracts, return an empty array []

Output ONLY a valid JSON array. No markdown, no explanation.

Schema for each opportunity:
{
  "description": "Detailed description of the research opportunity (50+ chars)",
  "required_equipment": ["list of equipment needed"],
  "required_techniques": ["list of techniques needed"],
  "required_expertise": ["list of expertise areas needed"],
  "estimated_complexity": "low" | "medium" | "high",
  "concreteness_score": 0.0-1.0,
  "source_paper_indices": [0, 1]
}

source_paper_indices refers to the 0-based index of the paper(s) in the input list that this opportunity comes from."""

QUALITY_THRESHOLD = 0.5


async def extract_opportunities(
    session: AsyncSession,
    lab_id: uuid.UUID,
    papers: list[Paper],
    settings: Settings | None = None,
) -> list[Opportunity]:
    """Extract research opportunities from a set of papers.

    Args:
        session: Database session
        lab_id: Lab UUID
        papers: Papers to extract opportunities from
        settings: App settings

    Returns:
        List of stored Opportunity models
    """
    if settings is None:
        settings = get_settings()

    if not papers:
        return []

    all_opportunities: list[Opportunity] = []

    # Process papers in batches of 5
    for i in range(0, len(papers), 5):
        batch = papers[i : i + 5]
        batch_opps = await _extract_batch(
            session, lab_id, batch, i, settings
        )
        all_opportunities.extend(batch_opps)

    # Generate embeddings for accepted opportunities (best-effort)
    if all_opportunities:
        with contextlib.suppress(Exception):
            await _generate_opportunity_embeddings(session, all_opportunities, settings)

    return all_opportunities


async def _extract_batch(
    session: AsyncSession,
    lab_id: uuid.UUID,
    papers: list[Paper],
    batch_offset: int,
    settings: Settings,
) -> list[Opportunity]:
    """Extract opportunities from a batch of papers."""
    # Format papers for prompt
    papers_text = "\n\n".join(
        f"Paper {i} (PMID: {p.pmid or 'N/A'}, DOI: {p.doi or 'N/A'}):\n"
        f"Title: {p.title}\n"
        f"Abstract: {p.abstract}"
        for i, p in enumerate(papers)
    )

    user_prompt = f"""Extract concrete research opportunities from these abstracts:

{papers_text}

Output a JSON array of opportunities (or empty array if none found):"""

    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
    )

    response_text = response.choices[0].message.content.strip()

    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        raw_opportunities = json.loads(response_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_opportunities, list):
        return []

    # Filter by quality and store
    opportunities: list[Opportunity] = []
    for raw_opp in raw_opportunities:
        concreteness = raw_opp.get("concreteness_score", 0.0)
        if concreteness < QUALITY_THRESHOLD:
            continue

        # Map source_paper_indices back to actual paper IDs
        source_indices = raw_opp.get("source_paper_indices", [])
        source_paper_ids = [
            papers[idx].id
            for idx in source_indices
            if 0 <= idx < len(papers)
        ]
        if not source_paper_ids:
            # Default to all papers in this batch
            source_paper_ids = [p.id for p in papers]

        opp = Opportunity(
            lab_id=lab_id,
            description=raw_opp.get("description", ""),
            required_equipment=raw_opp.get("required_equipment", []),
            required_techniques=raw_opp.get("required_techniques", []),
            required_expertise=raw_opp.get("required_expertise", []),
            estimated_complexity=raw_opp.get("estimated_complexity", "medium"),
            source_paper_ids=source_paper_ids,
            extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
            llm_model=settings.llm_model,
            quality_score=concreteness,
        )
        session.add(opp)
        opportunities.append(opp)

    await session.flush()
    return opportunities


async def _generate_opportunity_embeddings(
    session: AsyncSession,
    opportunities: list[Opportunity],
    settings: Settings,
) -> None:
    """Generate and store embeddings for opportunities."""
    texts = [opp.description for opp in opportunities]

    response = await aembedding(
        model=settings.embedding_model,
        input=texts,
    )

    for i, opp in enumerate(opportunities):
        embedding = response.data[i]["embedding"]
        await session.execute(
            text("UPDATE opportunities SET embedding = :embedding WHERE id = :id"),
            {"embedding": str(embedding), "id": opp.id},
        )

    await session.flush()


async def extract_opportunities_from_abstracts(
    abstracts: list[dict[str, str]],
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Standalone extraction for eval harness (no DB dependency).

    Args:
        abstracts: List of dicts with 'title' and 'abstract' keys
        settings: App settings

    Returns:
        List of raw opportunity dicts (not stored in DB)
    """
    if settings is None:
        settings = get_settings()

    papers_text = "\n\n".join(
        f"Paper {i}:\nTitle: {a['title']}\nAbstract: {a['abstract']}"
        for i, a in enumerate(abstracts)
    )

    user_prompt = f"""Extract concrete research opportunities from these abstracts:

{papers_text}

Output a JSON array of opportunities (or empty array if none found):"""

    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
    )

    response_text = response.choices[0].message.content.strip()

    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        raw_opportunities = json.loads(response_text)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_opportunities, list):
        return []

    # Apply quality filter
    return [
        opp for opp in raw_opportunities
        if opp.get("concreteness_score", 0.0) >= QUALITY_THRESHOLD
    ]
