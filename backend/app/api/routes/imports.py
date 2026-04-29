"""Lab state import endpoints — ORCID-driven publication import.

POST   /api/v1/labs/{lab_id}/imports/orcid                     enqueue an import
GET    /api/v1/labs/{lab_id}/imports/{import_id}               poll status + proposed state
POST   /api/v1/labs/{lab_id}/imports/{import_id}/commit        accept selected items
DELETE /api/v1/labs/{lab_id}/imports/{import_id}               cancel an in-flight import
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.audit import log_audit_event
from app.models.lab_state_import import (
    IMPORT_STATUS_CANCELLED,
    IMPORT_STATUS_COMMITTED,
    IMPORT_STATUS_QUEUED,
    IMPORT_STATUS_REVIEW,
    LabStateImport,
)
from app.schemas.lab_state_import import (
    AcceptedLabState,
    ImportProgress,
    LabStateImportCommit,
    LabStateImportCreate,
    LabStateImportResponse,
    ProposedLabState,
)

router = APIRouter()


def _enqueue(import_id: uuid.UUID) -> None:
    """Defer the Celery import to keep route imports light at test time."""
    from app.tasks.import_orcid import import_lab_state_from_orcid

    import_lab_state_from_orcid.delay(str(import_id))


def _to_response(row: LabStateImport) -> LabStateImportResponse:
    progress = ImportProgress.model_validate(row.progress or {})
    proposed = (
        ProposedLabState.model_validate(row.proposed_state)
        if row.proposed_state is not None
        else None
    )
    return LabStateImportResponse(
        id=row.id,
        lab_id=row.lab_id,
        orcid_id=row.orcid_id,
        status=row.status,  # type: ignore[arg-type]
        progress=progress,
        proposed_state=proposed,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


@router.post(
    "/{lab_id}/imports/orcid",
    response_model=LabStateImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_orcid_import(
    body: LabStateImportCreate,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabStateImportResponse:
    """Start an ORCID-driven import. Returns immediately with the import row to poll."""
    row = LabStateImport(
        lab_id=lab.id,
        user_id=user.user_id,
        orcid_id=body.orcid_id,
        status=IMPORT_STATUS_QUEUED,
        progress={"current_step": "Queued"},
    )
    session.add(row)
    await session.flush()

    await log_audit_event(
        session=session,
        user_id=user.user_id,
        lab_id=lab.id,
        action="POST",
        resource_type="lab_state_imports",
        resource_id=row.id,
        details={"orcid_id": body.orcid_id},
    )

    # Commit so the Celery worker (separate session) can see the row.
    await session.commit()

    _enqueue(row.id)
    return _to_response(row)


@router.get(
    "/{lab_id}/imports/{import_id}",
    response_model=LabStateImportResponse,
)
async def get_import(
    import_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabStateImportResponse:
    """Return the current state of an import. Used by frontend polling."""
    result = await session.execute(
        select(LabStateImport).where(
            LabStateImport.id == import_id,
            LabStateImport.lab_id == lab.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found",
        )
    return _to_response(row)


@router.post(
    "/{lab_id}/imports/{import_id}/commit",
    response_model=LabStateImportResponse,
)
async def commit_import(
    import_id: uuid.UUID,
    body: LabStateImportCommit,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabStateImportResponse:
    """Accept the user-trimmed selection and write it through distillation.

    Each accepted item is converted into a `RawSignal` (signal_type='document'),
    then the existing distillation engine compresses the resulting state. This
    re-uses the audited, eval-gated path rather than writing `lab_states`
    directly — important because matching depends on token budget + embeddings,
    which `run_distillation` already handles.
    """
    result = await session.execute(
        select(LabStateImport).where(
            LabStateImport.id == import_id,
            LabStateImport.lab_id == lab.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found",
        )
    if row.status != IMPORT_STATUS_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Import is in status '{row.status}', cannot commit.",
        )

    await _commit_accepted_to_lab_state(
        session=session,
        lab_id=lab.id,
        user_id=user.user_id,
        accepted=body.accepted,
        orcid_id=row.orcid_id,
    )

    row.status = IMPORT_STATUS_COMMITTED
    row.completed_at = datetime.now(UTC)

    await log_audit_event(
        session=session,
        user_id=user.user_id,
        lab_id=lab.id,
        action="POST",
        resource_type="lab_state_imports",
        resource_id=row.id,
        details={"event": "commit", "accepted_counts": _count_accepted(body.accepted)},
    )
    await session.commit()
    return _to_response(row)


@router.delete(
    "/{lab_id}/imports/{import_id}",
    response_model=LabStateImportResponse,
)
async def cancel_import(
    import_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabStateImportResponse:
    """Mark an import as cancelled. Allowed from any non-terminal status."""
    result = await session.execute(
        select(LabStateImport).where(
            LabStateImport.id == import_id,
            LabStateImport.lab_id == lab.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found",
        )
    if row.status in {IMPORT_STATUS_COMMITTED, IMPORT_STATUS_CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel import in terminal status '{row.status}'.",
        )

    row.status = IMPORT_STATUS_CANCELLED
    row.completed_at = datetime.now(UTC)
    await session.commit()
    return _to_response(row)


async def _commit_accepted_to_lab_state(
    session: AsyncSession,
    lab_id: uuid.UUID,
    user_id: str,
    accepted: AcceptedLabState,
    orcid_id: str,
) -> None:
    """Convert accepted items into a single RawSignal and run distillation.

    We bundle the whole accepted selection into one signal of type 'document'
    (the closest existing semantic) rather than spamming the signal table. The
    distillation prompt already merges with current state, so re-imports are
    additive — no special-cased merge logic needed here.
    """
    # Lazy imports avoid pulling Celery + LiteLLM into the route module at
    # FastAPI startup (and break a circular import via tasks/__init__).
    from app.models.signal import RawSignal
    from app.services.distillation import run_distillation

    signal_content = {
        "source": "orcid_import",
        "orcid_id": orcid_id,
        "accepted": accepted.model_dump(),
    }
    signal = RawSignal(
        lab_id=lab_id,
        signal_type="document",
        content=signal_content,
        processed=False,
        created_by=user_id,
    )
    session.add(signal)
    await session.flush()

    await run_distillation(
        session=session,
        lab_id=lab_id,
        signal_ids=[signal.id],
    )


def _count_accepted(accepted: AcceptedLabState) -> dict[str, int]:
    return {
        "equipment": len(accepted.equipment),
        "techniques": len(accepted.techniques),
        "expertise": len(accepted.expertise),
        "organisms": len(accepted.organisms),
        "reagents": len(accepted.reagents),
    }
