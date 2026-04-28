"""API tests for the directions and strengthen agent endpoints.

Reuses the FakeSession + override pattern from test_reviewer.py. Each
agent has its own enqueue function, so each is patched independently.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_lab, get_db_session
from app.main import app
from app.models.agent import (
    AGENT_PURPOSE_DIRECTIONS,
    AGENT_PURPOSE_STRENGTHEN,
    AGENT_STATUS_COMPLETE,
    AGENT_STATUS_QUEUED,
    AgentMessage,
    AgentSession,
)
from app.models.lab import Lab

# Reuse the fake-store helpers from the reviewer test module — they're
# behaviorally generic, just imported by the same test paths in CI.
from tests.api.test_reviewer import _FakeSession  # type: ignore[import-untyped]


@pytest.fixture
def fake_lab() -> Lab:
    return Lab(id=uuid.uuid4(), clerk_org_id="test_org", name="Test Lab")


@pytest.fixture
def agents_client(client: TestClient, fake_lab: Lab):  # type: ignore[no-untyped-def]
    """Generic fixture — patches both directions + strengthen enqueues."""
    store = _FakeSession()

    async def override_db() -> Any:
        yield store

    async def override_lab() -> Lab:
        return fake_lab

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_lab] = override_lab
    try:
        with (
            patch("app.api.routes.agents._enqueue_directions"),
            patch("app.api.routes.agents._enqueue_strengthen"),
        ):
            yield client, fake_lab, store
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_lab, None)


# ---------- Directions ----------


def test_directions_post_creates_queued_session(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = agents_client
    with patch("app.api.routes.agents._enqueue_directions") as enqueue:
        resp = client.post(
            f"/api/v1/labs/{lab.id}/directions",
            json={"input_text": "neurodegeneration"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    sid = uuid.UUID(body["session_id"])
    saved = store._sessions[sid]
    assert saved.purpose == AGENT_PURPOSE_DIRECTIONS
    assert saved.input_text == "neurodegeneration"
    assert saved.status == AGENT_STATUS_QUEUED
    enqueue.assert_called_once_with(sid)


def test_directions_post_accepts_empty_input(agents_client) -> None:  # type: ignore[no-untyped-def]
    """Directions agent allows an empty focus area — it draws focus from
    the lab state when nothing is provided."""
    client, lab, store = agents_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/directions",
        json={"input_text": ""},
    )
    assert resp.status_code == 201, resp.text
    sid = uuid.UUID(resp.json()["session_id"])
    assert store._sessions[sid].input_text == ""


def test_directions_post_rejects_oversized_input(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = agents_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/directions",
        json={"input_text": "a" * 2001},
    )
    assert resp.status_code in (422, 400)


def test_directions_get_returns_session(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = agents_client
    sid = uuid.uuid4()
    store.seed_session(
        AgentSession(
            id=sid,
            lab_id=lab.id,
            user_id="u",
            purpose=AGENT_PURPOSE_DIRECTIONS,
            input_text="neurodegeneration",
            status=AGENT_STATUS_COMPLETE,
            final_answer="1. Direction one ...",
            turn_count=4,
        )
    )
    store.seed_message(
        AgentMessage(
            id=uuid.uuid4(),
            session_id=sid,
            seq=1,
            role="user",
            content="neurodegeneration",
        )
    )
    resp = client.get(f"/api/v1/labs/{lab.id}/directions/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_answer"] == "1. Direction one ..."
    assert body["turn_count"] == 4


# ---------- Strengthen ----------


def test_strengthen_post_creates_queued_session(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = agents_client
    with patch("app.api.routes.agents._enqueue_strengthen") as enqueue:
        resp = client.post(
            f"/api/v1/labs/{lab.id}/strengthen",
            json={"input_text": "x" * 60},
        )
    assert resp.status_code == 201, resp.text
    sid = uuid.UUID(resp.json()["session_id"])
    saved = store._sessions[sid]
    assert saved.purpose == AGENT_PURPOSE_STRENGTHEN
    enqueue.assert_called_once_with(sid)


def test_strengthen_post_rejects_short_input(agents_client) -> None:  # type: ignore[no-untyped-def]
    """Strengthen requires ≥40 chars — too short to ground a recommendation."""
    client, lab, _ = agents_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/strengthen",
        json={"input_text": "x" * 39},
    )
    assert resp.status_code in (422, 400)


def test_strengthen_post_rejects_oversized_input(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = agents_client
    resp = client.post(
        f"/api/v1/labs/{lab.id}/strengthen",
        json={"input_text": "a" * 4001},
    )
    assert resp.status_code in (422, 400)


def test_strengthen_get_returns_session(agents_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, store = agents_client
    sid = uuid.uuid4()
    store.seed_session(
        AgentSession(
            id=sid,
            lab_id=lab.id,
            user_id="u",
            purpose=AGENT_PURPOSE_STRENGTHEN,
            input_text="x" * 60,
            status=AGENT_STATUS_COMPLETE,
            final_answer="1. Run a Western to confirm ...",
            turn_count=5,
        )
    )
    resp = client.get(f"/api/v1/labs/{lab.id}/strengthen/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_answer"].startswith("1. Run a Western")
