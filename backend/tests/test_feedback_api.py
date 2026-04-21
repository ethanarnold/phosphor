"""Tests for the Phase 4 feedback endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_lab, get_db_session
from app.main import app
from app.models.lab import Lab
from app.models.opportunity import Opportunity


class _FakeSession:
    def __init__(self, opportunity: Opportunity | None = None) -> None:
        self.added: list[object] = []
        self._opportunity = opportunity

    def add(self, obj: object) -> None:
        from app.models.signal import RawSignal

        if isinstance(obj, RawSignal):
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(UTC)
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, _query):  # type: ignore[no-untyped-def]
        class _Res:
            def __init__(self, opp):  # type: ignore[no-untyped-def]
                self._opp = opp

            def scalar_one_or_none(self):  # type: ignore[no-untyped-def]
                return self._opp

        return _Res(self._opportunity)


@pytest.fixture
def fake_lab() -> Lab:
    return Lab(id=uuid.uuid4(), clerk_org_id="test_org", name="Test Lab")


@pytest.fixture
def fake_opportunity(fake_lab: Lab) -> Opportunity:
    return Opportunity(
        id=uuid.uuid4(),
        lab_id=fake_lab.id,
        description="Try cryo-EM on sample X",
        required_equipment=[],
        required_techniques=[],
        required_expertise=[],
        estimated_complexity="medium",
        source_paper_ids=[],
        status="active",
    )


@pytest.fixture
def feedback_client(client: TestClient, fake_lab: Lab, fake_opportunity: Opportunity):  # type: ignore[no-untyped-def]
    session = _FakeSession(opportunity=fake_opportunity)

    async def override_db():  # type: ignore[no-untyped-def]
        yield session

    async def override_lab() -> Lab:
        return fake_lab

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_lab] = override_lab
    try:
        yield client, fake_lab, fake_opportunity, session
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_lab, None)


def test_state_correction_emits_signal(feedback_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _, session = feedback_client
    with patch("app.api.routes.feedback._queue_distill"):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/feedback/state",
            json={
                "correction_type": "remove",
                "field": "equipment",
                "item_name": "ancient microscope",
                "reason": "sold it",
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["correction"]["item_name"] == "ancient microscope"
    assert body["signal_id"]
    assert len(session.added) == 1


def test_accept_opportunity_marks_accepted_and_emits_signal(feedback_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, opp, session = feedback_client
    with patch("app.api.routes.feedback._queue_distill"):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/feedback/opportunities/{opp.id}",
            json={"decision": "accept"},
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["decision"] == "accept"
    assert opp.status == "accepted"


def test_reject_opportunity_marks_dismissed(feedback_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, opp, _ = feedback_client
    with patch("app.api.routes.feedback._queue_distill"):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/feedback/opportunities/{opp.id}",
            json={"decision": "reject", "reason": "out of scope"},
        )
    assert resp.status_code == 201
    assert opp.status == "dismissed"


def test_opportunity_feedback_404_when_missing(client: TestClient, fake_lab: Lab) -> None:
    session = _FakeSession(opportunity=None)

    async def override_db():  # type: ignore[no-untyped-def]
        yield session

    async def override_lab() -> Lab:
        return fake_lab

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_lab] = override_lab
    try:
        resp = client.post(
            f"/api/v1/labs/{fake_lab.id}/feedback/opportunities/{uuid.uuid4()}",
            json={"decision": "accept"},
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_lab, None)
