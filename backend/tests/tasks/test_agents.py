"""Unit tests for the reviewer Celery task.

We patch `task_session` to yield a stub session, the LiteLLM completion
to a canned response, and the tool registry to a no-op — the task is
responsible only for wiring (loading the session, marking running, calling
run_agent with a DbRecorder, finalizing). The loop and tools have their
own coverage.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.loop import AgentResult
from app.models.agent import (
    AGENT_PURPOSE_REVIEWER,
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_ERROR,
    AGENT_STATUS_QUEUED,
    AgentMessage,
    AgentSession,
)
from app.tasks.agents import _run_agent_async


class _FakeSession:
    def __init__(self, session_row: AgentSession | None) -> None:
        self._row = session_row
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj: Any) -> None:
        if isinstance(obj, AgentMessage) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, stmt: Any) -> Any:
        class _Res:
            def __init__(self, row: Any) -> None:
                self._row = row

            def scalar_one_or_none(self) -> Any:
                return self._row

        # Only select(AgentSession).where(id=...) matters here.
        return _Res(self._row)


def _seeded_session(sid: uuid.UUID, lab_id: uuid.UUID) -> AgentSession:
    return AgentSession(
        id=sid,
        lab_id=lab_id,
        user_id="u",
        purpose=AGENT_PURPOSE_REVIEWER,
        input_text="x" * 40,
        status=AGENT_STATUS_QUEUED,
        turn_count=0,
    )


@pytest.mark.asyncio
async def test_task_marks_running_runs_agent_and_finalizes() -> None:
    sid = uuid.uuid4()
    lab_id = uuid.uuid4()
    row = _seeded_session(sid, lab_id)
    fake_db = _FakeSession(row)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    run_agent_mock = AsyncMock(
        return_value=AgentResult(
            final_answer="grounded critique body",
            tool_calls=[],
            messages=[],
            turn_count=3,
            stop_reason="complete",
        )
    )

    with (
        patch("app.tasks.agents.task_session", fake_task_session),
        patch("app.tasks.agents.run_agent", run_agent_mock),
        patch("app.tasks.agents.build_default_registry", return_value=SimpleNamespace()),
        patch("app.tasks.agents.load_prompt", return_value="SYS"),
    ):
        result = await _run_agent_async(str(sid), purpose="reviewer")

    assert result["status"] == AGENT_STATUS_COMPLETE
    assert result["turn_count"] == 3
    assert row.status == AGENT_STATUS_COMPLETE
    assert row.final_answer == "grounded critique body"
    run_agent_mock.assert_awaited_once()
    assert run_agent_mock.await_args.kwargs["system_prompt"] == "SYS"
    assert run_agent_mock.await_args.kwargs["user_message"] == "x" * 40


@pytest.mark.asyncio
async def test_task_records_error_when_loop_crashes() -> None:
    sid = uuid.uuid4()
    row = _seeded_session(sid, uuid.uuid4())
    fake_db = _FakeSession(row)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    with (
        patch("app.tasks.agents.task_session", fake_task_session),
        patch(
            "app.tasks.agents.run_agent",
            side_effect=RuntimeError("provider down"),
        ),
        patch("app.tasks.agents.build_default_registry", return_value=SimpleNamespace()),
        patch("app.tasks.agents.load_prompt", return_value="SYS"),
    ):
        result = await _run_agent_async(str(sid), purpose="reviewer")

    assert result["status"] == "error"
    assert row.status == AGENT_STATUS_ERROR
    assert row.error is not None
    assert "provider down" in row.error


@pytest.mark.asyncio
async def test_task_short_circuits_on_missing_session() -> None:
    fake_db = _FakeSession(None)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    with patch("app.tasks.agents.task_session", fake_task_session):
        result = await _run_agent_async(str(uuid.uuid4()), purpose="reviewer")
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_task_loads_correct_prompt_for_purpose() -> None:
    """The generic task selects its prompt by purpose. A row created with
    purpose=directions must load the directions prompt, not reviewer."""
    sid = uuid.uuid4()
    row = AgentSession(
        id=sid,
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose="directions",
        input_text="",
        status=AGENT_STATUS_QUEUED,
        turn_count=0,
    )
    fake_db = _FakeSession(row)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    load_prompt_mock = AsyncMock(return_value="DIRECTIONS-SYS")  # noqa: F841 — sanity unused
    with (
        patch("app.tasks.agents.task_session", fake_task_session),
        patch(
            "app.tasks.agents.run_agent",
            new=AsyncMock(
                return_value=AgentResult(
                    final_answer="1. Direction one ...",
                    tool_calls=[],
                    messages=[],
                    turn_count=4,
                    stop_reason="complete",
                )
            ),
        ),
        patch("app.tasks.agents.build_default_registry", return_value=SimpleNamespace()),
        patch("app.tasks.agents.load_prompt") as load_prompt_patch,
    ):
        load_prompt_patch.return_value = "DIRECTIONS-SYS"
        result = await _run_agent_async(str(sid), purpose="directions")

    assert result["status"] == AGENT_STATUS_COMPLETE
    load_prompt_patch.assert_called_once_with("directions")


@pytest.mark.asyncio
async def test_task_rejects_purpose_mismatch() -> None:
    """If the row's purpose != task's purpose, the task short-circuits
    rather than running the wrong prompt against the wrong intent."""
    sid = uuid.uuid4()
    row = AgentSession(
        id=sid,
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose=AGENT_PURPOSE_REVIEWER,  # row says reviewer
        input_text="x" * 40,
        status=AGENT_STATUS_QUEUED,
        turn_count=0,
    )
    fake_db = _FakeSession(row)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    with patch("app.tasks.agents.task_session", fake_task_session):
        result = await _run_agent_async(str(sid), purpose="directions")

    assert result["status"] == "error"
    assert "purpose mismatch" in result["error"]


@pytest.mark.asyncio
async def test_task_marks_error_on_max_turns() -> None:
    sid = uuid.uuid4()
    row = _seeded_session(sid, uuid.uuid4())
    fake_db = _FakeSession(row)

    @asynccontextmanager
    async def fake_task_session():
        yield fake_db

    with (
        patch("app.tasks.agents.task_session", fake_task_session),
        patch(
            "app.tasks.agents.run_agent",
            new=AsyncMock(
                return_value=AgentResult(
                    final_answer=None,
                    tool_calls=[],
                    messages=[],
                    turn_count=8,
                    stop_reason="max_turns",
                    error="Agent did not conclude within 8 turns",
                )
            ),
        ),
        patch("app.tasks.agents.build_default_registry", return_value=SimpleNamespace()),
        patch("app.tasks.agents.load_prompt", return_value="SYS"),
    ):
        result = await _run_agent_async(str(sid), purpose="reviewer")

    assert result["stop_reason"] == "max_turns"
    assert row.status == AGENT_STATUS_ERROR
    assert "8 turns" in (row.error or "")
