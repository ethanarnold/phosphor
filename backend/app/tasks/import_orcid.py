"""Celery task that drives an ORCID-based lab state import end-to-end.

Pipeline:
    ORCID Public API → DOI list → sort newest-first, cap at MAX_PAPERS
    → PubMed efetch (abstracts + MeSH) → per-paper LLM extraction
    → aggregate with provenance → write `proposed_state`, set status=review.

Progress is written to the `lab_state_imports.progress` JSONB column so the
frontend's polling endpoint can render "Reading 23 of 50…" without waiting
for the whole task to finish.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy import text as sa_text

from app.core.config import get_settings
from app.core.database import task_session
from app.models.lab_state_import import (
    IMPORT_STATUS_EXTRACTING,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_FETCHING,
    IMPORT_STATUS_REVIEW,
    LabStateImport,
)
from app.services.capability_extraction import (
    EXTRACTION_PROMPT_VERSION,
    aggregate_capabilities,
    extract_capabilities_from_paper,
)
from app.services.orcid import OrcidClient, OrcidError
from app.services.pubmed import PubMedClient
from app.tasks import celery_app

# Cap papers per import. Bounds latency (~1 min at concurrency=5) and cost
# (~$1 on Sonnet at ~3k tokens-in / ~1k tokens-out per paper). Older papers
# reflect lab capabilities less, so newest-first triage is also cheaper-better.
MAX_PAPERS = 50
EXTRACTION_CONCURRENCY = 5


@celery_app.task(bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def import_lab_state_from_orcid(self: Any, import_id: str) -> dict[str, Any]:
    """Drive an ORCID import from a queued `lab_state_imports` row."""
    return asyncio.run(_run_import_async(import_id))


async def _run_import_async(import_id: str) -> dict[str, Any]:
    iid = uuid.UUID(import_id)
    settings = get_settings()

    async with task_session() as session:
        # The task runs without `app.current_org_id` set, so RLS would filter
        # this row out. Disable per-statement; safe because we operate only on
        # the supplied import_id (which the API created under tenancy).
        await session.execute(sa_text("SET LOCAL row_security = off"))

        row = await _load_import(session, iid)
        if row is None:
            return {"status": "not_found", "import_id": import_id}

        try:
            # ---- Phase 1: fetch ORCID works ----
            row.status = IMPORT_STATUS_FETCHING
            row.progress = {"current_step": "Fetching publications from ORCID…"}
            await session.commit()

            async with httpx.AsyncClient() as http:
                orcid = OrcidClient(http)
                works = await orcid.fetch_works(row.orcid_id)

            if not works:
                row.status = IMPORT_STATUS_FAILED
                row.error = "No public works found for this ORCID iD."
                row.completed_at = datetime.now(UTC)
                await session.commit()
                return {"status": "failed", "import_id": import_id, "reason": "no_works"}

            # Sort newest-first, take top MAX_PAPERS, prefer DOI lookups.
            works.sort(key=lambda w: (w.get("year") or 0), reverse=True)
            works = works[:MAX_PAPERS]
            dois = [w["doi"] for w in works if w.get("doi")]

            # ---- Phase 2: PubMed efetch ----
            row.progress = {
                "current_step": "Fetching abstracts from PubMed…",
                "papers_total": len(works),
                "papers_processed": 0,
            }
            await session.commit()

            async with httpx.AsyncClient() as http:
                pubmed = PubMedClient(http, api_key=settings.pubmed_api_key)
                papers = await pubmed.fetch_by_dois(dois) if dois else []

            if not papers:
                row.status = IMPORT_STATUS_FAILED
                row.error = (
                    "Found ORCID works but none had abstracts indexed in PubMed. "
                    "Try a researcher with biomedical publications."
                )
                row.completed_at = datetime.now(UTC)
                await session.commit()
                return {"status": "failed", "import_id": import_id, "reason": "no_pubmed_hits"}

            # ---- Phase 3: per-paper LLM extraction ----
            row.status = IMPORT_STATUS_EXTRACTING
            row.progress = {
                "current_step": "Reading papers and extracting capabilities…",
                "papers_total": len(papers),
                "papers_processed": 0,
            }
            row.prompt_version = EXTRACTION_PROMPT_VERSION
            await session.commit()

            extractions = await _extract_chunked(
                session, row, papers, EXTRACTION_CONCURRENCY
            )

            # ---- Phase 4: aggregate + persist for review ----
            proposed = aggregate_capabilities(extractions, papers)
            row.proposed_state = proposed.model_dump(mode="json")
            row.status = IMPORT_STATUS_REVIEW
            row.progress = {
                "current_step": "Ready for review",
                "papers_total": len(papers),
                "papers_processed": len(papers),
            }
            row.completed_at = datetime.now(UTC)
            await session.commit()

            return {
                "status": IMPORT_STATUS_REVIEW,
                "import_id": import_id,
                "papers_processed": len(papers),
            }

        except OrcidError as exc:
            row.status = IMPORT_STATUS_FAILED
            row.error = str(exc)[:2000]
            row.completed_at = datetime.now(UTC)
            await session.commit()
            return {"status": "failed", "import_id": import_id, "reason": "orcid_error"}
        except Exception as exc:  # noqa: BLE001 — record & return; do not re-raise
            row.status = IMPORT_STATUS_FAILED
            row.error = f"Import crashed: {exc}"[:2000]
            row.completed_at = datetime.now(UTC)
            await session.commit()
            return {"status": "failed", "import_id": import_id, "reason": "exception"}


async def _extract_chunked(
    session: Any,
    row: LabStateImport,
    papers: list[dict[str, Any]],
    concurrency: int,
) -> list[Any]:
    """Run extraction in fixed-size chunks, committing progress after each chunk.

    Equivalent throughput to a single asyncio.gather over the whole list, but
    gives the frontend a steady stream of progress updates (one commit every
    ~5 papers / ~5 seconds at sonnet latencies).
    """
    extractions: list[Any] = []
    settings = get_settings()
    for i in range(0, len(papers), concurrency):
        chunk = papers[i : i + concurrency]
        chunk_results = await asyncio.gather(
            *(_safe_extract(p, settings) for p in chunk),
        )
        extractions.extend(chunk_results)
        # Persist incremental progress so the API GET reflects movement.
        row.progress = {
            **(row.progress or {}),
            "papers_processed": len(extractions),
        }
        await session.commit()
    return extractions


async def _safe_extract(paper: dict[str, Any], settings: Any) -> Any:
    """One paper's extraction — never raises; bad output is just empty."""
    from app.services.capability_extraction import CapabilityExtraction

    try:
        return await extract_capabilities_from_paper(paper, settings)
    except Exception:  # noqa: BLE001
        return CapabilityExtraction()


async def _load_import(session: Any, iid: uuid.UUID) -> LabStateImport | None:
    result = await session.execute(
        select(LabStateImport).where(LabStateImport.id == iid)
    )
    row: LabStateImport | None = result.scalar_one_or_none()
    return row


__all__ = ["import_lab_state_from_orcid"]
