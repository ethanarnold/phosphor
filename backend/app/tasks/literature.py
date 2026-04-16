"""Celery tasks for literature scanning and opportunity extraction."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.core.database import task_session
from app.models.literature_scan import LiteratureScan
from app.models.paper import Paper
from app.services.extraction import extract_opportunities
from app.services.literature import ingest_literature
from app.tasks import celery_app


@celery_app.task(bind=True, max_retries=3)
def run_literature_scan(
    self: Any,
    lab_id: str,
    scan_id: str,
    scan_params: dict[str, Any],
) -> dict[str, Any]:
    """Full literature scan pipeline: ingest papers then extract opportunities.

    Args:
        lab_id: Lab UUID string
        scan_id: LiteratureScan UUID string
        scan_params: Scan parameters dict (query_terms, mesh_terms, etc.)

    Returns:
        Dict with result information
    """
    try:
        result = asyncio.run(
            _run_scan_async(lab_id, scan_id, scan_params)
        )
        return result
    except Exception as e:
        # Mark scan as failed before retrying
        asyncio.run(_mark_scan_failed(scan_id, str(e)))
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 30) from e


async def _run_scan_async(
    lab_id: str,
    scan_id: str,
    scan_params: dict[str, Any],
) -> dict[str, Any]:
    """Async implementation of the full scan pipeline."""
    lab_uuid = uuid.UUID(lab_id)
    scan_uuid = uuid.UUID(scan_id)

    async with task_session() as session:
        # Update scan status to ingesting
        await session.execute(
            update(LiteratureScan)
            .where(LiteratureScan.id == scan_uuid)
            .values(status="ingesting")
        )
        await session.commit()

    async with task_session() as session:
        # Step 1: Ingest literature
        counts = await ingest_literature(
            session=session,
            lab_id=lab_uuid,
            query_terms=scan_params.get("query_terms", []),
            mesh_terms=scan_params.get("mesh_terms"),
            field_of_study=scan_params.get("field_of_study"),
            max_results=scan_params.get("max_results", 100),
            sources=scan_params.get("sources"),
        )

        # Update scan with ingestion counts
        await session.execute(
            update(LiteratureScan)
            .where(LiteratureScan.id == scan_uuid)
            .values(
                status="extracting",
                papers_found=counts["papers_found"],
                papers_new=counts["papers_new"],
            )
        )
        await session.commit()

    async with task_session() as session:
        # Step 2: Extract opportunities from new papers
        # Get the most recently added papers for this lab
        result = await session.execute(
            select(Paper)
            .where(Paper.lab_id == lab_uuid)
            .order_by(Paper.created_at.desc())
            .limit(counts["papers_new"])
        )
        new_papers = list(result.scalars().all())

        opportunities: list[Any] = []
        if new_papers:
            opportunities = await extract_opportunities(
                session=session,
                lab_id=lab_uuid,
                papers=new_papers,
            )

        # Mark scan as completed
        await session.execute(
            update(LiteratureScan)
            .where(LiteratureScan.id == scan_uuid)
            .values(
                status="completed",
                opportunities_extracted=len(opportunities),
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()

    return {
        "status": "completed",
        "lab_id": lab_id,
        "scan_id": scan_id,
        "papers_found": counts["papers_found"],
        "papers_new": counts["papers_new"],
        "opportunities_extracted": len(opportunities),
    }


async def _mark_scan_failed(scan_id: str, error: str) -> None:
    """Mark a scan as failed."""
    scan_uuid = uuid.UUID(scan_id)
    async with task_session() as session:
        await session.execute(
            update(LiteratureScan)
            .where(LiteratureScan.id == scan_uuid)
            .values(
                status="failed",
                error_message=error[:1000],
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()


@celery_app.task
def scheduled_literature_scan() -> dict[str, Any]:
    """Celery beat task: scan literature for all labs with configured search interests."""
    result = asyncio.run(_run_scheduled_scans())
    return result


async def _run_scheduled_scans() -> dict[str, Any]:
    """Query all labs with search_config and queue individual scans."""
    from app.models.lab import Lab

    async with task_session() as session:
        result = await session.execute(
            select(Lab).where(Lab.search_config.isnot(None))
        )
        labs = result.scalars().all()

        queued = 0
        for lab in labs:
            if not lab.search_config:
                continue

            # Create a scan record
            scan = LiteratureScan(
                lab_id=lab.id,
                scan_type="scheduled",
                query_params=lab.search_config,
                status="pending",
                triggered_by="system",
            )
            session.add(scan)
            await session.flush()

            # Queue the scan task
            run_literature_scan.delay(
                str(lab.id),
                str(scan.id),
                lab.search_config,
            )
            queued += 1

        await session.commit()

    return {
        "status": "completed",
        "labs_scanned": queued,
    }
