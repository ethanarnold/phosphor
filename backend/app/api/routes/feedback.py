"""Feedback endpoints — one-click opportunity decisions and state corrections.

Every correction emits a RawSignal (type=correction) so the distillation
engine incorporates it on the next run — this is the feedback loop that
lets users teach the system without manual state editing.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.security import AuthenticatedUser, require_role
from app.models.opportunity import Opportunity
from app.models.signal import RawSignal
from app.schemas.feedback import (
    FeedbackResponse,
    OpportunityFeedback,
    StateCorrection,
)

router = APIRouter()


def _queue_distill(lab_id: str, signal_id: str) -> None:
    from app.tasks.distill import distill_lab_state

    distill_lab_state.delay(lab_id, [signal_id])


@router.post(
    "/{lab_id}/feedback/state",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_state_correction(
    correction: StateCorrection,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> FeedbackResponse:
    """Record an inline lab-state correction as a signal."""
    signal = RawSignal(
        lab_id=lab.id,
        signal_type="correction",
        content=json.loads(correction.model_dump_json()),
        created_by=user.user_id,
    )
    session.add(signal)
    await session.flush()
    _queue_distill(str(lab.id), str(signal.id))

    return FeedbackResponse(
        signal_id=signal.id,
        correction=correction,
        created_at=signal.created_at or datetime.now(UTC),
    )


@router.post(
    "/{lab_id}/feedback/opportunities/{opp_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_opportunity_feedback(
    opp_id: uuid.UUID,
    feedback: OpportunityFeedback,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> FeedbackResponse:
    """Accept or reject an opportunity. Updates status and emits a signal
    so future distillation/matching can weight similar opportunities."""
    opp = (
        await session.execute(
            select(Opportunity).where(
                Opportunity.id == opp_id,
                Opportunity.lab_id == lab.id,
            )
        )
    ).scalar_one_or_none()
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    opp.status = "accepted" if feedback.decision == "accept" else "dismissed"

    signal = RawSignal(
        lab_id=lab.id,
        signal_type="correction",
        content={
            "correction_type": "update",
            "field": "resource_constraints",
            "item_name": f"opportunity:{opp_id}",
            "new_value": {
                "decision": feedback.decision,
                "opportunity_description": opp.description[:500],
            },
            "reason": feedback.reason,
        },
        created_by=user.user_id,
    )
    session.add(signal)
    await session.flush()
    _queue_distill(str(lab.id), str(signal.id))

    return FeedbackResponse(
        signal_id=signal.id,
        opportunity_id=opp_id,
        decision=feedback.decision,
        created_at=signal.created_at or datetime.now(UTC),
    )
