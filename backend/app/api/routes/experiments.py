"""Experiment entry endpoints — Phase 4 input surfaces."""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, require_role
from app.schemas.experiment import (
    BulkExperimentRequest,
    BulkExperimentResponse,
    ExperimentCreateResponse,
    ExperimentEntry,
    QuickLogRequest,
)
from app.services.experiments import create_experiment_signal, parse_quick_log
from app.services.metrics import record_event

router = APIRouter()


async def _record_adoption(
    *,
    session: AsyncSession,
    lab_id: uuid.UUID,
    user_id: str,
    event_type: str,
    duration_ms: int | None,
) -> None:
    """Best-effort instrumentation — never raise to the caller."""
    try:
        await record_event(
            session=session,
            lab_id=lab_id,
            event_type=event_type,
            user_id=user_id,
            duration_ms=duration_ms,
        )
    except Exception:  # noqa: BLE001 — metrics must not break ingestion
        return


def _queue_distill(lab_id: str, signal_id: str) -> None:
    from app.tasks.distill import distill_lab_state

    distill_lab_state.delay(lab_id, [signal_id])


@router.post(
    "/{lab_id}/experiments",
    response_model=ExperimentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    entry: ExperimentEntry,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> ExperimentCreateResponse:
    """Log a single structured experiment."""
    start = time.perf_counter()
    signal = await create_experiment_signal(
        session=session,
        lab_id=lab.id,
        created_by=user.user_id,
        entry=entry,
    )
    _queue_distill(str(lab.id), str(signal.id))
    elapsed = int((time.perf_counter() - start) * 1000)
    await _record_adoption(
        session=session,
        lab_id=lab.id,
        user_id=user.user_id,
        event_type="experiment.structured",
        duration_ms=elapsed,
    )
    return ExperimentCreateResponse(
        signal_id=signal.id,
        experiment=entry,
        elapsed_ms=elapsed,
    )


@router.post(
    "/{lab_id}/experiments/quick",
    response_model=ExperimentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def quick_log_experiment(
    req: QuickLogRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> ExperimentCreateResponse:
    """Parse a single free-text field into a structured experiment via LLM."""
    start = time.perf_counter()
    try:
        entry = await parse_quick_log(
            text=req.text,
            outcome_hint=req.outcome_hint,
            settings=get_settings(),
        )
    except Exception as exc:  # noqa: BLE001 — LLM/JSON failures should 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse quick-log: {exc}",
        ) from exc

    signal = await create_experiment_signal(
        session=session,
        lab_id=lab.id,
        created_by=user.user_id,
        entry=entry,
    )
    _queue_distill(str(lab.id), str(signal.id))
    elapsed = int((time.perf_counter() - start) * 1000)
    await _record_adoption(
        session=session,
        lab_id=lab.id,
        user_id=user.user_id,
        event_type="experiment.quick",
        duration_ms=elapsed,
    )
    return ExperimentCreateResponse(
        signal_id=signal.id,
        experiment=entry,
        elapsed_ms=elapsed,
    )


@router.post(
    "/{lab_id}/experiments/bulk",
    response_model=BulkExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_experiments(
    req: BulkExperimentRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> BulkExperimentResponse:
    """Bulk import pre-parsed experiment entries (e.g., from CSV on the client)."""
    created: list[ExperimentCreateResponse] = []
    failed: list[dict[str, str]] = []
    signal_ids: list[str] = []

    for idx, entry in enumerate(req.entries):
        try:
            signal = await create_experiment_signal(
                session=session,
                lab_id=lab.id,
                created_by=user.user_id,
                entry=entry,
            )
            signal_ids.append(str(signal.id))
            created.append(ExperimentCreateResponse(signal_id=signal.id, experiment=entry))
        except Exception as exc:  # noqa: BLE001 — per-row failure shouldn't abort batch
            failed.append({"index": str(idx), "error": str(exc)})

    if signal_ids:
        from app.tasks.distill import distill_lab_state

        distill_lab_state.delay(str(lab.id), signal_ids)

    return BulkExperimentResponse(created=created, failed=failed)
