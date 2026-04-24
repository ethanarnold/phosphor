"""Tests for agent persistence: DbRecorder emits messages in order,
finalize_session / mark_running transition status correctly, and the RLS
policy actually isolates labs at the Postgres level.

Unit tests use a FakeSession stand-in. The RLS test opens a real DB
connection — it skips when the CI Postgres (`DATABASE_URL`) is unreachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.agents.loop import AgentResult
from app.agents.persistence import DbRecorder, finalize_session, mark_running
from app.core.database import Base
from app.models.agent import (
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_ERROR,
    AGENT_STATUS_QUEUED,
    AGENT_STATUS_RUNNING,
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_SYSTEM,
    MESSAGE_ROLE_TOOL,
    MESSAGE_ROLE_USER,
    AgentMessage,
    AgentSession,
)
from app.models.lab import Lab

# ---------- Unit tests with a FakeSession ----------


class _FakeSession:
    """Minimal AsyncSession stand-in for unit tests."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flush_count = 0

    def add(self, obj: Any) -> None:
        if isinstance(obj, AgentMessage) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_recorder_writes_messages_in_seq_order() -> None:
    session = _FakeSession()
    recorder = DbRecorder(session=session, agent_session_id=uuid.uuid4())  # type: ignore[arg-type]

    await recorder.on_system("sys prompt")
    await recorder.on_user("please review")
    await recorder.on_assistant_tool_calls(
        None,
        [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "get_lab_state", "arguments": "{}"},
            }
        ],
    )
    await recorder.on_tool_result(
        tool_name="get_lab_state",
        arguments={},
        result={"version": 3},
        error=None,
    )
    await recorder.on_final_assistant("here is the critique")

    msgs = [m for m in session.added if isinstance(m, AgentMessage)]
    # 5 rows: system, user, one assistant (one tool_call), one tool, one final assistant.
    assert [m.seq for m in msgs] == [1, 2, 3, 4, 5]
    assert [m.role for m in msgs] == [
        MESSAGE_ROLE_SYSTEM,
        MESSAGE_ROLE_USER,
        MESSAGE_ROLE_ASSISTANT,
        MESSAGE_ROLE_TOOL,
        MESSAGE_ROLE_ASSISTANT,
    ]
    # Tool-call assistant row carries name + args.
    tc_row = msgs[2]
    assert tc_row.tool_name == "get_lab_state"
    assert tc_row.tool_args_json == {}
    # Tool-result row carries the dispatched result.
    tool_row = msgs[3]
    assert tool_row.tool_name == "get_lab_state"
    assert tool_row.tool_result_json == {"result": {"version": 3}}


@pytest.mark.asyncio
async def test_recorder_emits_one_assistant_row_per_tool_call() -> None:
    """A single model turn that emits multiple parallel tool_calls should
    persist as multiple assistant rows — so the UI can render them as a list."""
    session = _FakeSession()
    recorder = DbRecorder(session=session, agent_session_id=uuid.uuid4())  # type: ignore[arg-type]

    await recorder.on_assistant_tool_calls(
        "thinking",
        [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "get_lab_state", "arguments": "{}"},
            },
            {
                "id": "c2",
                "type": "function",
                "function": {
                    "name": "search_experiments",
                    "arguments": '{"query": "CRISPR"}',
                },
            },
        ],
    )
    msgs = [m for m in session.added if isinstance(m, AgentMessage)]
    assert len(msgs) == 2
    assert msgs[0].tool_name == "get_lab_state"
    assert msgs[1].tool_name == "search_experiments"
    assert msgs[1].tool_args_json == {"query": "CRISPR"}
    # Seqs must be distinct and monotonic.
    assert msgs[0].seq < msgs[1].seq


@pytest.mark.asyncio
async def test_recorder_tolerates_malformed_arguments_json() -> None:
    session = _FakeSession()
    recorder = DbRecorder(session=session, agent_session_id=uuid.uuid4())  # type: ignore[arg-type]

    await recorder.on_assistant_tool_calls(
        None,
        [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "x", "arguments": "{not json"},
            }
        ],
    )
    msgs = [m for m in session.added if isinstance(m, AgentMessage)]
    # Fallback: store raw under `_raw` so the trace is inspectable.
    assert msgs[0].tool_args_json == {"_raw": "{not json"}


@pytest.mark.asyncio
async def test_recorder_stores_tool_errors_under_error_key() -> None:
    session = _FakeSession()
    recorder = DbRecorder(session=session, agent_session_id=uuid.uuid4())  # type: ignore[arg-type]

    await recorder.on_tool_result(
        tool_name="explode",
        arguments={},
        result={"error": "boom"},
        error="Tool execution failed: boom",
    )
    msgs = [m for m in session.added if isinstance(m, AgentMessage)]
    assert msgs[0].role == MESSAGE_ROLE_TOOL
    assert msgs[0].tool_result_json is not None
    assert "error" in msgs[0].tool_result_json
    assert msgs[0].tool_result_json["result"] == {"error": "boom"}


@pytest.mark.asyncio
async def test_mark_running_sets_status_and_model() -> None:
    session = _FakeSession()
    s = AgentSession(
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose="reviewer",
        input_text="aim",
    )
    s.status = AGENT_STATUS_QUEUED
    await mark_running(session, s, model="claude-sonnet-4-6")  # type: ignore[arg-type]
    assert s.status == AGENT_STATUS_RUNNING
    assert s.model == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_finalize_session_marks_complete_on_success() -> None:
    session = _FakeSession()
    s = AgentSession(
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose="reviewer",
        input_text="aim",
    )
    result = AgentResult(
        final_answer="here is the critique",
        tool_calls=[],
        messages=[],
        turn_count=3,
        stop_reason="complete",
    )
    await finalize_session(session, s, result)  # type: ignore[arg-type]
    assert s.status == AGENT_STATUS_COMPLETE
    assert s.final_answer == "here is the critique"
    assert s.error is None
    assert s.turn_count == 3
    assert s.completed_at is not None


@pytest.mark.asyncio
async def test_finalize_session_marks_error_on_max_turns() -> None:
    session = _FakeSession()
    s = AgentSession(
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose="reviewer",
        input_text="aim",
    )
    result = AgentResult(
        final_answer=None,
        tool_calls=[],
        messages=[],
        turn_count=8,
        stop_reason="max_turns",
        error="Agent did not conclude within 8 turns",
    )
    await finalize_session(session, s, result)  # type: ignore[arg-type]
    assert s.status == AGENT_STATUS_ERROR
    assert s.error is not None
    assert "8 turns" in s.error
    assert s.final_answer is None


@pytest.mark.asyncio
async def test_finalize_session_truncates_overlong_error() -> None:
    session = _FakeSession()
    s = AgentSession(
        lab_id=uuid.uuid4(),
        user_id="u",
        purpose="reviewer",
        input_text="aim",
    )
    result = AgentResult(
        final_answer=None,
        tool_calls=[],
        messages=[],
        turn_count=1,
        stop_reason="error",
        error="x" * 5000,
    )
    await finalize_session(session, s, result)  # type: ignore[arg-type]
    assert s.error is not None
    assert len(s.error) <= 2000


# ---------- Integration test: RLS enforces tenant isolation ----------


TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://phosphor:phosphor@localhost:5432/phosphor_test",
)


async def _db_available() -> bool:
    try:
        engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except (OperationalError, Exception):
        return False


def _skip_without_db() -> None:
    if not asyncio.get_event_loop().run_until_complete(_db_available()):
        pytest.skip("Postgres not available; RLS test requires a live DB.")


@pytest_asyncio.fixture
async def rls_db() -> Any:
    """Spin up a fresh schema with RLS policies installed, return a session factory.

    Creates all tables via `Base.metadata.create_all`, then installs the
    production RLS policies for `agent_sessions`/`agent_messages` so tests
    exercise the same isolation contract a real deployment would.
    """
    if not await _db_available():
        pytest.skip("Postgres not available; RLS test requires a live DB.")

    engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY"))
        await conn.execute(
            text(
                """CREATE POLICY agent_sessions_isolation ON agent_sessions
                USING (lab_id IN (
                    SELECT id FROM labs
                    WHERE clerk_org_id = current_setting('app.current_org_id', true)
                ))"""
            )
        )
        await conn.execute(
            text(
                """CREATE POLICY agent_messages_isolation ON agent_messages
                USING (session_id IN (
                    SELECT s.id FROM agent_sessions s
                    JOIN labs l ON l.id = s.lab_id
                    WHERE l.clerk_org_id = current_setting('app.current_org_id', true)
                ))"""
            )
        )

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield Session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_rls_isolates_agent_sessions_between_labs(rls_db: Any) -> None:
    Session = rls_db

    # Seed two labs with distinct clerk_org_ids (no RLS on labs — just setup).
    async with Session() as setup:
        lab_a = Lab(id=uuid.uuid4(), clerk_org_id="org_A", name="Lab A")
        lab_b = Lab(id=uuid.uuid4(), clerk_org_id="org_B", name="Lab B")
        setup.add(lab_a)
        setup.add(lab_b)
        await setup.commit()
        sess_a_id = uuid.uuid4()
        sess_b_id = uuid.uuid4()
        await setup.execute(text("SET LOCAL app.current_org_id = 'org_A'"))
        setup.add(
            AgentSession(
                id=sess_a_id,
                lab_id=lab_a.id,
                user_id="u_a",
                purpose="reviewer",
                input_text="aim A",
            )
        )
        await setup.commit()
        await setup.execute(text("SET LOCAL app.current_org_id = 'org_B'"))
        setup.add(
            AgentSession(
                id=sess_b_id,
                lab_id=lab_b.id,
                user_id="u_b",
                purpose="reviewer",
                input_text="aim B",
            )
        )
        await setup.commit()

    # Confirm: when scoped to org_A, the session for org_B is invisible.
    async with Session() as s:
        await s.execute(text("SET LOCAL app.current_org_id = 'org_A'"))
        from sqlalchemy import select

        rows = (await s.execute(select(AgentSession))).scalars().all()
        assert {r.id for r in rows} == {sess_a_id}

    # And vice versa.
    async with Session() as s:
        await s.execute(text("SET LOCAL app.current_org_id = 'org_B'"))
        from sqlalchemy import select

        rows = (await s.execute(select(AgentSession))).scalars().all()
        assert {r.id for r in rows} == {sess_b_id}


@pytest.mark.asyncio
async def test_rls_isolates_agent_messages_between_labs(rls_db: Any) -> None:
    Session = rls_db

    async with Session() as setup:
        lab_a = Lab(id=uuid.uuid4(), clerk_org_id="org_A", name="Lab A")
        lab_b = Lab(id=uuid.uuid4(), clerk_org_id="org_B", name="Lab B")
        setup.add(lab_a)
        setup.add(lab_b)
        await setup.commit()

        await setup.execute(text("SET LOCAL app.current_org_id = 'org_A'"))
        sa = AgentSession(
            id=uuid.uuid4(),
            lab_id=lab_a.id,
            user_id="u",
            purpose="reviewer",
            input_text="aim",
        )
        setup.add(sa)
        await setup.flush()
        setup.add(AgentMessage(session_id=sa.id, seq=1, role="user", content="hello A"))
        await setup.commit()

        await setup.execute(text("SET LOCAL app.current_org_id = 'org_B'"))
        sb = AgentSession(
            id=uuid.uuid4(),
            lab_id=lab_b.id,
            user_id="u",
            purpose="reviewer",
            input_text="aim",
        )
        setup.add(sb)
        await setup.flush()
        setup.add(AgentMessage(session_id=sb.id, seq=1, role="user", content="hello B"))
        await setup.commit()

    async with Session() as s:
        await s.execute(text("SET LOCAL app.current_org_id = 'org_A'"))
        from sqlalchemy import select

        rows = (await s.execute(select(AgentMessage))).scalars().all()
        contents = {r.content for r in rows}
        assert "hello A" in contents
        assert "hello B" not in contents
