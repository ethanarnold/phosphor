"""Tests for Phase 4 experiment endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_lab, get_db_session
from app.main import app
from app.models.lab import Lab
from app.schemas.experiment import ExperimentEntry


class _FakeSession:
    """Minimal async session stand-in for handler flow.

    The experiments endpoints only call `.add()` and `.flush()`. We populate
    the signal's id and lab_id on add so the response model can serialize.
    """

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        from app.models.signal import RawSignal

        if isinstance(obj, RawSignal) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    async def flush(self) -> None:  # noqa: D401 — async stub
        return None


@pytest.fixture
def fake_lab() -> Lab:
    lab = Lab(id=uuid.uuid4(), clerk_org_id="test_org", name="Test Lab")
    return lab


@pytest.fixture
def experiments_client(client: TestClient, fake_lab: Lab):  # type: ignore[no-untyped-def]
    fake_session = _FakeSession()

    async def override_db_session():  # type: ignore[no-untyped-def]
        yield fake_session

    async def override_current_lab() -> Lab:
        return fake_lab

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_lab] = override_current_lab
    try:
        yield client, fake_lab, fake_session
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_lab, None)


def test_create_experiment_structured(experiments_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = experiments_client
    with patch("app.api.routes.experiments._queue_distill"):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/experiments",
            json={
                "technique": "Western blot",
                "outcome": "success",
                "notes": "Clean bands at 42kDa",
                "equipment_used": ["iBlot 2"],
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["experiment"]["technique"] == "Western blot"
    assert body["signal_id"]
    assert body["elapsed_ms"] is not None


def test_quick_log_uses_llm_parse(experiments_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = experiments_client
    parsed = ExperimentEntry(technique="qPCR", outcome="partial", notes="some replicates noisy")
    with (
        patch(
            "app.api.routes.experiments.parse_quick_log",
            new=AsyncMock(return_value=parsed),
        ),
        patch("app.api.routes.experiments._queue_distill"),
    ):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/experiments/quick",
            json={"text": "ran qPCR today, some wells looked noisy"},
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["experiment"]["technique"] == "qPCR"


def test_quick_log_parse_failure_returns_422(experiments_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = experiments_client
    with patch(
        "app.api.routes.experiments.parse_quick_log",
        new=AsyncMock(side_effect=ValueError("bad json")),
    ):
        resp = client.post(
            f"/api/v1/labs/{lab.id}/experiments/quick",
            json={"text": "nonsense"},
        )
    assert resp.status_code == 422


def test_bulk_experiments_partial_failure(experiments_client) -> None:  # type: ignore[no-untyped-def]
    client, lab, _ = experiments_client
    entries = [
        {"technique": "PCR", "outcome": "success", "notes": "ok"},
        {"technique": "Gel", "outcome": "failed", "notes": "smeared"},
    ]
    with patch("app.tasks.distill.distill_lab_state") as mock_task:
        mock_task.delay = lambda *a, **k: None
        resp = client.post(
            f"/api/v1/labs/{lab.id}/experiments/bulk",
            json={"entries": entries},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created"]) == 2
    assert body["failed"] == []
