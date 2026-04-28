"""API tests for the reviewer agent endpoints.

Uses the existing `client` fixture's auth override and a FakeSession
stand-in — no Postgres required. Celery is patched so `.delay()` is a noop
(the task itself is tested separately in `tests/tasks/test_agents.py`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_lab, get_db_session
from app.main import app
from app.models.agent import (
    AGENT_PURPOSE_REVIEWER,
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_QUEUED,
    AgentMessage,
    AgentSession,
)
from app.models.lab import Lab


class _FakeSession:
    """Async session stub with an in-memory store of AgentSession/Message rows."""

    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, AgentSession] = {}
        self._messages: list[AgentMessage] = []
        self.commits = 0

    # --- SA-like mutators ---
    def add(self, obj: Any) -> None:
        if isinstance(obj, AgentSession):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            if obj.turn_count is None:
                obj.turn_count = 0
            self._sessions[obj.id] = obj
        elif isinstance(obj, AgentMessage):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(UTC)
            self._messages.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    # --- query shim: intercept a few shapes we exercise ---
    async def execute(self, stmt: Any) -> Any:
        return _FakeResult(self, stmt)

    # Helpers for tests
    def seed_session(self, s: AgentSession) -> None:
        self.add(s)

    def seed_message(self, m: AgentMessage) -> None:
        self.add(m)


import re as _re

_UUID_RE = _re.compile(
    r"'?(" r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" r"|[0-9a-f]{32}" r")'?"
)


def _uuids_in_stmt(stmt: Any) -> list[uuid.UUID]:
    """Pull every UUID literal out of a compiled SQL statement, in textual order.

    SQLAlchemy renders UUIDs without dashes via `literal_binds=True` (32 hex
    chars); we accept both styles.
    """
    try:
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
    except Exception:
        return []
    return [uuid.UUID(m) for m in _UUID_RE.findall(str(compiled))]


def _stmt_targets_model(stmt: Any, model: Any) -> bool:
    try:
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    except Exception:
        return False
    return model.__tablename__ in compiled


class _FakeResult:
    def __init__(self, store: _FakeSession, stmt: Any) -> None:
        self._store = store
        self._stmt = stmt

    def scalar_one_or_none(self) -> Any:
        uuids = _uuids_in_stmt(self._stmt)
        if _stmt_targets_model(self._stmt, AgentSession) and uuids:
            # The GET handler's query has filters: id == sid, lab_id == lab.id, purpose == ...
            candidate_ids = set(uuids)
            for s in self._store._sessions.values():
                if s.id in candidate_ids and s.lab_id in candidate_ids:
                    return s
        return None

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        uuids = _uuids_in_stmt(self._stmt)
        if _stmt_targets_model(self._stmt, AgentMessage) and uuids:
            sid = uuids[0]
            msgs = [m for m in self._store._messages if m.session_id == sid]
            msgs.sort(key=lambda m: m.seq)
            return msgs
        return []

    def __iter__(self):  # type: ignore[no-untyped-def]
        yield from self.all()


@pytest.fixture
def fake_lab() -> Lab:
    return Lab(id=uuid.uuid4(), clerk_org_id="test_org", name="Test Lab")


@pytest.fixture
def reviewer_client(client: TestClient, fake_lab: Lab):  # type: ignore[no-untyped-def]
    store = _FakeSession()

    async def override_db():  # type: ignore[no-untyped-def]
        yield store

    async def override_lab() -> Lab:
        return fake_lab

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_lab] = override_lab
    try:
        with patch("app.api.routes.agents._enqueue_reviewer"):
            yield client, fake_lab, store
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_lab, None)


# -------------------------- POST ----------------------------


def test_post_creates_queued_session_and_enqueues_task(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = reviewer_client
    with patch("app.api.routes.agents._enqueue_reviewer") as enqueue:
        resp = client.post(
            f"/api/v1/labs/{lab.id}/reviewer",
            json={"input_text": "x" * 40},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == AGENT_STATUS_QUEUED
    sid = uuid.UUID(body["session_id"])
    assert sid in store._sessions
    saved = store._sessions[sid]
    assert saved.lab_id == lab.id
    assert saved.purpose == AGENT_PURPOSE_REVIEWER
    assert saved.status == AGENT_STATUS_QUEUED
    enqueue.assert_called_once_with(sid)
    # The route commits so the Celery worker can read the row.
    assert store.commits >= 1


def test_post_rejects_short_input(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = reviewer_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/reviewer",
        json={"input_text": "too short"},
    )
    assert resp.status_code in (422, 400)


def test_post_rejects_oversized_input(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = reviewer_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/reviewer",
        json={"input_text": "a" * 4001},
    )
    assert resp.status_code in (422, 400)


def test_post_requires_authentication() -> None:
    """Without the `client` fixture's auth override, the endpoint must 401."""
    from unittest.mock import AsyncMock

    from app.core.security import get_current_user

    app.dependency_overrides.pop(get_current_user, None)
    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        TestClient(app) as raw_client,
    ):
        resp = raw_client.post(
            f"/api/v1/labs/{uuid.uuid4()}/reviewer",
            json={"input_text": "x" * 40},
        )
    # 401 from auth, or 403 if Clerk middleware rejects.
    assert resp.status_code in (401, 403)


# -------------------------- GET ----------------------------


def test_get_returns_session_with_trace(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = reviewer_client

    sid = uuid.uuid4()
    store.seed_session(
        AgentSession(
            id=sid,
            lab_id=lab.id,
            user_id="u",
            purpose=AGENT_PURPOSE_REVIEWER,
            input_text="aim " * 10,
            status=AGENT_STATUS_COMPLETE,
            final_answer="critique body",
            turn_count=3,
            model="claude-sonnet-4-6",
        )
    )
    store.seed_message(
        AgentMessage(
            id=uuid.uuid4(),
            session_id=sid,
            seq=1,
            role="user",
            content="aim " * 10,
        )
    )
    store.seed_message(
        AgentMessage(
            id=uuid.uuid4(),
            session_id=sid,
            seq=2,
            role="assistant",
            content=None,
            tool_name="get_lab_state",
            tool_args_json={},
        )
    )
    store.seed_message(
        AgentMessage(
            id=uuid.uuid4(),
            session_id=sid,
            seq=3,
            role="tool",
            tool_name="get_lab_state",
            tool_args_json={},
            tool_result_json={"result": {"version": 1}},
        )
    )
    store.seed_message(
        AgentMessage(
            id=uuid.uuid4(),
            session_id=sid,
            seq=4,
            role="assistant",
            content="critique body",
        )
    )

    resp = client.get(f"/api/v1/labs/{lab.id}/reviewer/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == AGENT_STATUS_COMPLETE
    assert body["final_answer"] == "critique body"
    assert body["turn_count"] == 3
    assert len(body["messages"]) == 4
    # Trace is seq-ordered.
    assert [m["seq"] for m in body["messages"]] == [1, 2, 3, 4]
    assert body["messages"][1]["tool_name"] == "get_lab_state"
    assert body["messages"][2]["tool_result_json"] == {"result": {"version": 1}}


def test_get_missing_session_returns_404(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = reviewer_client
    resp = client.get(f"/api/v1/labs/{lab.id}/reviewer/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_session_from_another_lab_returns_404(reviewer_client) -> None:  # type: ignore[no-untyped-def]
    """A session belonging to another lab must not be discoverable —
    same 404 as a missing session, no existence leak."""
    client, lab, store = reviewer_client
    other_lab_id = uuid.uuid4()
    sid = uuid.uuid4()
    store.seed_session(
        AgentSession(
            id=sid,
            lab_id=other_lab_id,
            user_id="u",
            purpose=AGENT_PURPOSE_REVIEWER,
            input_text="aim " * 10,
            status=AGENT_STATUS_COMPLETE,
        )
    )
    resp = client.get(f"/api/v1/labs/{lab.id}/reviewer/{sid}")
    assert resp.status_code == 404
