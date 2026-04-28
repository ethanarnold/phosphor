"""Agent endpoints — reviewer, directions, strengthen.

Each agent gets two endpoints:

  POST  /api/v1/labs/{lab_id}/{purpose}          — enqueue a run
  GET   /api/v1/labs/{lab_id}/{purpose}/{sid}    — poll for status + trace

All three agents share a session model and a tool-calling loop; only the
prompt and the input contract differ.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.models.agent import (
    AGENT_PURPOSE_DIRECTIONS,
    AGENT_PURPOSE_REVIEWER,
    AGENT_PURPOSE_STRENGTHEN,
    AGENT_STATUS_QUEUED,
    AgentMessage,
    AgentSession,
)
from app.schemas.agent import (
    AgentCreateResponse,
    AgentDetailResponse,
    AgentMessageView,
    DirectionsCreateRequest,
    ReviewerCreateRequest,
    StrengthenCreateRequest,
)

router = APIRouter()


def _enqueue_reviewer(session_id: uuid.UUID) -> None:
    from app.tasks.agents import run_reviewer_agent

    run_reviewer_agent.delay(str(session_id))


def _enqueue_directions(session_id: uuid.UUID) -> None:
    from app.tasks.agents import run_directions_agent

    run_directions_agent.delay(str(session_id))


def _enqueue_strengthen(session_id: uuid.UUID) -> None:
    from app.tasks.agents import run_strengthen_agent

    run_strengthen_agent.delay(str(session_id))


async def _create_agent_session(
    *,
    lab_id: uuid.UUID,
    user_id: str,
    purpose: str,
    input_text: str,
    session: DbSession,
) -> AgentSession:
    agent_session = AgentSession(
        lab_id=lab_id,
        user_id=user_id,
        purpose=purpose,
        input_text=input_text,
        status=AGENT_STATUS_QUEUED,
    )
    session.add(agent_session)
    await session.flush()
    # Commit so the Celery worker (separate DB session) can see the row.
    await session.commit()
    return agent_session


async def _load_agent_session(
    *,
    session_id: uuid.UUID,
    lab_id: uuid.UUID,
    purpose: str,
    session: DbSession,
) -> AgentDetailResponse:
    """Return the session detail or raise 404. Tenancy is checked twice:
    once via the explicit `lab_id` filter (so we never leak existence of a
    cross-lab session) and once at the row level via RLS."""
    result = await session.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.lab_id == lab_id,
            AgentSession.purpose == purpose,
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

    return AgentDetailResponse(
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


# ---------- Reviewer ----------


@router.post(
    "/{lab_id}/reviewer",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reviewer_session(
    body: ReviewerCreateRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentCreateResponse:
    """Start a reviewer run. Returns immediately with a session_id to poll."""
    agent_session = await _create_agent_session(
        lab_id=lab.id,
        user_id=user.user_id,
        purpose=AGENT_PURPOSE_REVIEWER,
        input_text=body.input_text,
        session=session,
    )
    _enqueue_reviewer(agent_session.id)
    return AgentCreateResponse(
        session_id=agent_session.id,
        status=AGENT_STATUS_QUEUED,  # type: ignore[arg-type]
    )


@router.get(
    "/{lab_id}/reviewer/{session_id}",
    response_model=AgentDetailResponse,
)
async def get_reviewer_session(
    session_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentDetailResponse:
    return await _load_agent_session(
        session_id=session_id,
        lab_id=lab.id,
        purpose=AGENT_PURPOSE_REVIEWER,
        session=session,
    )


# ---------- Directions ----------


@router.post(
    "/{lab_id}/directions",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_directions_session(
    body: DirectionsCreateRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentCreateResponse:
    """Start a directions run. Empty input is allowed — the agent draws
    focus from the lab state when no constraint is supplied."""
    agent_session = await _create_agent_session(
        lab_id=lab.id,
        user_id=user.user_id,
        purpose=AGENT_PURPOSE_DIRECTIONS,
        input_text=body.input_text,
        session=session,
    )
    _enqueue_directions(agent_session.id)
    return AgentCreateResponse(
        session_id=agent_session.id,
        status=AGENT_STATUS_QUEUED,  # type: ignore[arg-type]
    )


@router.get(
    "/{lab_id}/directions/{session_id}",
    response_model=AgentDetailResponse,
)
async def get_directions_session(
    session_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentDetailResponse:
    return await _load_agent_session(
        session_id=session_id,
        lab_id=lab.id,
        purpose=AGENT_PURPOSE_DIRECTIONS,
        session=session,
    )


# ---------- Strengthen ----------


@router.post(
    "/{lab_id}/strengthen",
    response_model=AgentCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_strengthen_session(
    body: StrengthenCreateRequest,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentCreateResponse:
    """Start a strengthen run on a project description."""
    agent_session = await _create_agent_session(
        lab_id=lab.id,
        user_id=user.user_id,
        purpose=AGENT_PURPOSE_STRENGTHEN,
        input_text=body.input_text,
        session=session,
    )
    _enqueue_strengthen(agent_session.id)
    return AgentCreateResponse(
        session_id=agent_session.id,
        status=AGENT_STATUS_QUEUED,  # type: ignore[arg-type]
    )


@router.get(
    "/{lab_id}/strengthen/{session_id}",
    response_model=AgentDetailResponse,
)
async def get_strengthen_session(
    session_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> AgentDetailResponse:
    return await _load_agent_session(
        session_id=session_id,
        lab_id=lab.id,
        purpose=AGENT_PURPOSE_STRENGTHEN,
        session=session,
    )
