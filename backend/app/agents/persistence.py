"""DB-backed implementation of the MessageRecorder protocol.

`DbRecorder` appends to `agent_messages` at each turn and flushes so the
frontend's polling endpoint can observe partial progress. Session-level
status transitions (`queued` → `running` → `complete`/`error`) are handled
by `mark_running` / `finalize_session`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.loop import AgentResult
from app.models.agent import (
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_ERROR,
    AGENT_STATUS_RUNNING,
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_SYSTEM,
    MESSAGE_ROLE_TOOL,
    MESSAGE_ROLE_USER,
    AgentMessage,
    AgentSession,
)


class DbRecorder:
    """Append messages to `agent_messages` as the loop runs."""

    def __init__(self, *, session: AsyncSession, agent_session_id: uuid.UUID) -> None:
        self._session = session
        self._agent_session_id = agent_session_id
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def _append(self, msg: AgentMessage) -> None:
        self._session.add(msg)
        await self._session.flush()

    async def on_system(self, content: str) -> None:
        await self._append(
            AgentMessage(
                session_id=self._agent_session_id,
                seq=self._next_seq(),
                role=MESSAGE_ROLE_SYSTEM,
                content=content,
            )
        )

    async def on_user(self, content: str) -> None:
        await self._append(
            AgentMessage(
                session_id=self._agent_session_id,
                seq=self._next_seq(),
                role=MESSAGE_ROLE_USER,
                content=content,
            )
        )

    async def on_assistant_tool_calls(
        self, content: str | None, tool_calls: list[dict[str, Any]]
    ) -> None:
        """Emit one assistant row per tool_call.

        The per-call row format (one assistant message carrying `tool_name` and
        `tool_args_json`) keeps the schema flat — no child tool_calls table —
        and makes the UI trace trivial to render as a list.
        """
        for tc in tool_calls:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            name = fn.get("name")
            raw_args = fn.get("arguments")
            args_json = _parse_args_for_storage(raw_args)
            await self._append(
                AgentMessage(
                    session_id=self._agent_session_id,
                    seq=self._next_seq(),
                    role=MESSAGE_ROLE_ASSISTANT,
                    content=content or None,
                    tool_name=name,
                    tool_args_json=args_json,
                )
            )

    async def on_tool_result(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        error: str | None,
    ) -> None:
        payload: dict[str, Any] = {"result": result}
        if error is not None:
            payload["error"] = error
        await self._append(
            AgentMessage(
                session_id=self._agent_session_id,
                seq=self._next_seq(),
                role=MESSAGE_ROLE_TOOL,
                tool_name=tool_name,
                tool_args_json=arguments,
                tool_result_json=_coerce_json_dict(payload),
            )
        )

    async def on_final_assistant(self, content: str | None) -> None:
        await self._append(
            AgentMessage(
                session_id=self._agent_session_id,
                seq=self._next_seq(),
                role=MESSAGE_ROLE_ASSISTANT,
                content=content or "",
            )
        )


def _parse_args_for_storage(raw: Any) -> dict[str, Any] | None:
    """Best-effort conversion of a tool_call arguments string into a dict."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        stripped = raw.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return {"_raw": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"_value": parsed}
    return {"_raw": str(raw)}


def _coerce_json_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Ensure a dict is JSON-safe for JSONB storage. Falls back to str() on failure."""
    import json

    try:
        json.dumps(value, default=str)
        return value
    except (TypeError, ValueError):
        return {k: str(v) for k, v in value.items()}


async def mark_running(session: AsyncSession, agent_session: AgentSession, *, model: str) -> None:
    agent_session.status = AGENT_STATUS_RUNNING
    agent_session.model = model
    await session.flush()


async def finalize_session(
    session: AsyncSession, agent_session: AgentSession, result: AgentResult
) -> None:
    """Copy terminal state from an AgentResult onto the DB row."""
    agent_session.turn_count = result.turn_count
    agent_session.completed_at = datetime.now(UTC)
    if result.stop_reason == "complete" and result.final_answer is not None:
        agent_session.status = AGENT_STATUS_COMPLETE
        agent_session.final_answer = _truncate(result.final_answer, 16000)
        agent_session.error = None
    else:
        agent_session.status = AGENT_STATUS_ERROR
        agent_session.error = _truncate(result.error or f"stopped: {result.stop_reason}", 2000)
    await session.flush()


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."
