"""Celery task for distillation."""

import asyncio
import uuid
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.distillation import get_unprocessed_signals, run_distillation
from app.tasks import celery_app


@celery_app.task(bind=True, max_retries=3)
def distill_lab_state(
    self: Any,
    lab_id: str,
    signal_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Celery task to run distillation for a lab.

    Args:
        lab_id: Lab UUID string
        signal_ids: Optional list of specific signal UUIDs to process.
                   If not provided, processes all unprocessed signals.

    Returns:
        Dict with result information
    """
    try:
        result = asyncio.run(
            _run_distillation_async(lab_id, signal_ids)
        )
        return result
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 10)


async def _run_distillation_async(
    lab_id: str,
    signal_ids: list[str] | None,
) -> dict[str, Any]:
    """Async implementation of distillation task."""
    lab_uuid = uuid.UUID(lab_id)

    async with AsyncSessionLocal() as session:
        # Get signals to process
        if signal_ids:
            ids = [uuid.UUID(s) for s in signal_ids]
        else:
            # Get unprocessed signals
            signals = await get_unprocessed_signals(session, lab_uuid)
            if not signals:
                return {
                    "status": "no_signals",
                    "message": "No unprocessed signals found",
                }
            ids = [s.id for s in signals]

        # Run distillation
        new_state = await run_distillation(session, lab_uuid, ids)

        await session.commit()

        return {
            "status": "completed",
            "lab_id": lab_id,
            "new_version": new_state.version,
            "token_count": new_state.token_count,
            "signals_processed": len(ids),
        }


@celery_app.task
def process_pending_signals() -> dict[str, Any]:
    """Scheduled task to process pending signals for all labs.

    This task can be scheduled via Celery Beat to run periodically.
    """
    # This would query all labs with unprocessed signals and
    # trigger distillation for each. Implementation depends on
    # desired batching strategy.
    return {"status": "not_implemented"}
