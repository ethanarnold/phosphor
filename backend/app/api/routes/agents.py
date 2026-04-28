"""Reviewer agent endpoints.

POST  /api/v1/labs/{lab_id}/reviewer          — enqueue a run
GET   /api/v1/labs/{lab_id}/reviewer/{sid}    — poll for status + trace
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.models.agent import (
    AGENT_PURPOSE_REVIEWER,
    AGENT_STATUS_QUEUED,
    AgentMessage,
    AgentSession,
)
from app.schemas.agent import (
    AgentMessageView,
    ReviewerCreateRequest,
    ReviewerCreateResponse,
    ReviewerDetailResponse,
)

router = APIRouter()


def _enqueue(session_id: uuid.UUID) -> None:
    """Defer the Celery import so route-import has no hard Celery dependency at test time."""
    from app.tasks.agents import run_reviewer_agent

    run_reviewer_agent.delay(str(session_id))


@router.post(
    "/{lab_id}/reviewer",
    response_model=ReviewerCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reviewer_session(
    body: ReviewerCreateRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> ReviewerCreateResponse:
    """Start a reviewer run. Returns immediately with a session_id to poll."""
    agent_session = AgentSession(
        lab_id=lab.id,
        user_id=user.user_id,
        purpose=AGENT_PURPOSE_REVIEWER,
        input_text=body.input_text,
        status=AGENT_STATUS_QUEUED,
    )
    session.add(agent_session)
    await session.flush()
    # Commit now so the Celery worker (separate DB session) can see the row.
    await session.commit()

    _enqueue(agent_session.id)

    return ReviewerCreateResponse(
        session_id=agent_session.id,
        status=AGENT_STATUS_QUEUED,  # type: ignore[arg-type]
    )


@router.get(
    "/{lab_id}/reviewer/{session_id}",
    response_model=ReviewerDetailResponse,
)
async def get_reviewer_session(
    session_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> ReviewerDetailResponse:
    """Return the current state of a reviewer session, including tool trace.

    404 on any mismatch — the `lab.id` check acts as the tenancy gate (RLS
    catches the rest at the row level). We do not surface existence of a
    session belonging to another lab.
    """
    result = await session.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.lab_id == lab.id,
            AgentSession.purpose == AGENT_PURPOSE_REVIEWER,
        )
    )
    agent_session = result.scalar_one_or_none()
    if agent_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages_result = await session.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == agent_session.id)
        .order_by(AgentMessage.seq)
    )
    messages = [AgentMessageView.model_validate(m) for m in messages_result.scalars()]

    return ReviewerDetailResponse(
        session_id=agent_session.id,
        status=agent_session.status,  # type: ignore[arg-type]
        input_text=agent_session.input_text,
        final_answer=agent_session.final_answer,
        error=agent_session.error,
        turn_count=agent_session.turn_count,
        model=agent_session.model,
        messages=messages,
        created_at=agent_session.created_at,
        completed_at=agent_session.completed_at,
    )
