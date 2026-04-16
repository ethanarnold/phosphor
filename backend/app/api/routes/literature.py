"""Literature scanning endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.security import AuthenticatedUser, require_role
from app.models.literature_scan import LiteratureScan
from app.schemas.literature_scan import ScanListResponse, ScanRequest, ScanResponse
from app.tasks.literature import run_literature_scan

router = APIRouter()


@router.post(
    "/{lab_id}/literature/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_scan(
    scan_request: ScanRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> LiteratureScan:
    """Trigger a manual literature scan for a lab.

    Queues a background task that fetches papers from PubMed and/or
    Semantic Scholar, deduplicates, and extracts research opportunities.
    """
    scan = LiteratureScan(
        lab_id=lab.id,
        scan_type="manual",
        query_params=scan_request.model_dump(),
        status="pending",
        triggered_by=user.user_id,
    )
    session.add(scan)
    await session.flush()

    # Queue the background scan task
    run_literature_scan.delay(
        str(lab.id),
        str(scan.id),
        scan_request.model_dump(),
    )

    return scan


@router.get(
    "/{lab_id}/literature/scans",
    response_model=ScanListResponse,
)
async def list_scans(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> ScanListResponse:
    """List literature scans for a lab."""
    query = select(LiteratureScan).where(LiteratureScan.lab_id == lab.id)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(LiteratureScan.started_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    scans = result.scalars().all()

    return ScanListResponse(
        scans=[ScanResponse.model_validate(s) for s in scans],
        total=total,
    )


@router.get(
    "/{lab_id}/literature/scans/{scan_id}",
    response_model=ScanResponse,
)
async def get_scan(
    scan_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LiteratureScan:
    """Get a specific scan's status and results."""
    result = await session.execute(
        select(LiteratureScan).where(
            LiteratureScan.id == scan_id,
            LiteratureScan.lab_id == lab.id,
        )
    )
    scan = result.scalar_one_or_none()

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    return scan
