"""Hybrid search service — keyword ILIKE + embedding similarity."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from litellm import aembedding
from sqlalchemy import String, cast, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.paper import Paper
from app.models.signal import RawSignal
from app.schemas.search import SearchHit


def _snippet(text: str, term: str, length: int = 240) -> str:
    if not text:
        return ""
    lower = text.lower()
    idx = lower.find(term.lower())
    if idx < 0:
        return text[:length]
    # Center the snippet on the match so the term is visible.
    half = max(0, (length - len(term)) // 2)
    start = max(0, idx - half)
    return text[start : start + length]


async def _embed_query(*, query: str, settings: Settings) -> list[float] | None:
    try:
        response = await aembedding(model=settings.embedding_model, input=query)
        return list(response.data[0]["embedding"])
    except Exception:
        return None


async def keyword_signals(
    *, session: AsyncSession, lab_id: uuid.UUID, query: str, limit: int
) -> list[SearchHit]:
    """ILIKE over the signal content cast to text."""
    like = f"%{query}%"
    q = (
        select(RawSignal)
        .where(
            RawSignal.lab_id == lab_id,
            cast(RawSignal.content, String).ilike(like),
        )
        .order_by(RawSignal.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(q)).scalars().all()
    hits: list[SearchHit] = []
    for r in rows:
        body = json.dumps(r.content) if isinstance(r.content, dict) else str(r.content)
        hits.append(
            SearchHit(
                kind="signal",
                id=r.id,
                score=1.0,
                snippet=_snippet(body, query),
                matched_by="keyword",
                signal_type=r.signal_type,
                created_at=r.created_at,
            )
        )
    return hits


async def keyword_papers(
    *, session: AsyncSession, lab_id: uuid.UUID, query: str, limit: int
) -> list[SearchHit]:
    like = f"%{query}%"
    q = (
        select(Paper)
        .where(
            Paper.lab_id == lab_id,
            (Paper.title.ilike(like)) | (Paper.abstract.ilike(like)),
        )
        .order_by(Paper.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(q)).scalars().all()
    return [
        SearchHit(
            kind="paper",
            id=p.id,
            score=1.0,
            snippet=_snippet(p.abstract or p.title, query),
            matched_by="keyword",
            title=p.title,
            created_at=p.created_at,
        )
        for p in rows
    ]


async def embedding_papers(
    *,
    session: AsyncSession,
    lab_id: uuid.UUID,
    embedding: list[float],
    limit: int,
) -> list[SearchHit]:
    """Cosine-similarity top-k over paper embeddings. Skips rows with NULL embedding."""
    emb_literal = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"
    sql = sa_text(
        """
        SELECT id, title, abstract, created_at,
               1 - (embedding <=> CAST(:emb AS vector)) AS score
        FROM papers
        WHERE lab_id = :lab_id AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:emb AS vector)
        LIMIT :limit
        """
    )
    result = await session.execute(
        sql,
        {"emb": emb_literal, "lab_id": str(lab_id), "limit": limit},
    )
    hits: list[SearchHit] = []
    for row in result.mappings():
        created_at = row.get("created_at") or datetime.now(UTC)
        hits.append(
            SearchHit(
                kind="paper",
                id=row["id"],
                score=float(row["score"]),
                snippet=(row["abstract"] or row["title"] or "")[:240],
                matched_by="embedding",
                title=row["title"],
                created_at=created_at,
            )
        )
    return hits


def merge_hits(*groups: list[SearchHit]) -> list[SearchHit]:
    """Deduplicate by (kind,id); mark matched_by='both' if present in multiple groups."""
    by_key: dict[tuple[str, str], SearchHit] = {}
    for group in groups:
        for hit in group:
            key = (hit.kind, str(hit.id))
            if key in by_key:
                prior = by_key[key]
                combined_score = max(prior.score, hit.score)
                prior_matched_by: Any = (
                    "both" if prior.matched_by != hit.matched_by else prior.matched_by
                )
                by_key[key] = prior.model_copy(
                    update={"score": combined_score, "matched_by": prior_matched_by}
                )
            else:
                by_key[key] = hit
    return sorted(by_key.values(), key=lambda h: h.score, reverse=True)


async def hybrid_search(
    *,
    session: AsyncSession,
    settings: Settings,
    lab_id: uuid.UUID,
    query: str,
    limit: int = 20,
) -> list[SearchHit]:
    per_kind = max(5, limit)
    kw_signals = await keyword_signals(session=session, lab_id=lab_id, query=query, limit=per_kind)
    kw_papers = await keyword_papers(session=session, lab_id=lab_id, query=query, limit=per_kind)

    embedding = await _embed_query(query=query, settings=settings)
    emb_papers: list[SearchHit] = []
    if embedding is not None:
        emb_papers = await embedding_papers(
            session=session, lab_id=lab_id, embedding=embedding, limit=per_kind
        )

    merged = merge_hits(kw_signals, kw_papers, emb_papers)
    return merged[:limit]
