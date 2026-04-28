"""Celery task that drives the reviewer agent end-to-end."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from app.agents import (
    DbRecorder,
    build_default_registry,
    finalize_session,
    mark_running,
    run_agent,
)
from app.agents.prompts import load_prompt
from app.core.config import get_settings
from app.core.database import task_session
from app.models.agent import AGENT_STATUS_ERROR, AgentSession
from app.tasks import celery_app


@celery_app.task(bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def run_reviewer_agent(self: Any, session_id: str) -> dict[str, Any]:
    """Drive a reviewer agent run from a queued `agent_sessions` row.

    No retries: an agent that fails should surface to the user, not re-run
    silently with partial state.
    """
    return asyncio.run(_run_reviewer_async(session_id))


async def _run_reviewer_async(session_id: str) -> dict[str, Any]:
    sid = uuid.UUID(session_id)
    settings = get_settings()

    async with task_session() as session:
        agent_session = await _load_session(session, sid)
        if agent_session is None:
            return {"status": "not_found", "session_id": session_id}

        try:
            await mark_running(session, agent_session, model=settings.llm_model)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": f"mark_running failed: {exc}"}

        registry = build_default_registry(
            session=session, settings=settings, lab_id=agent_session.lab_id
        )
        recorder = DbRecorder(session=session, agent_session_id=agent_session.id)
        system_prompt = load_prompt("reviewer")

        try:
            result = await run_agent(
                system_prompt=system_prompt,
                user_message=agent_session.input_text,
                registry=registry,
                model=settings.llm_model,
                recorder=recorder,
            )
        except Exception as exc:  # noqa: BLE001 — record & return; do not re-raise
            agent_session.status = AGENT_STATUS_ERROR
            agent_session.error = f"Agent crashed: {exc}"[:2000]
            await session.commit()
            return {"status": "error", "error": str(exc)}

        await finalize_session(session, agent_session, result)
        await session.commit()

        return {
            "status": agent_session.status,
            "session_id": session_id,
            "turn_count": result.turn_count,
            "stop_reason": result.stop_reason,
        }


async def _load_session(session: Any, sid: uuid.UUID) -> AgentSession | None:
    """Fetch the session without applying the tenant-scoped RLS filter.

    The task runs under a fresh DB connection without `app.current_org_id`
    set, so tenant policies evaluate to NULL and filter everything out.
    Disabling RLS here is safe because the task only ever acts on the
    `session_id` supplied by the API (which did run with tenancy), and all
    tool calls are still bound to that session's `lab_id`.
    """
    from sqlalchemy import text

    await session.execute(text("SET LOCAL row_security = off"))
    result = await session.execute(select(AgentSession).where(AgentSession.id == sid))
    row: AgentSession | None = result.scalar_one_or_none()
    return row
