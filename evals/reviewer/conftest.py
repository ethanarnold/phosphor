"""Reviewer eval fixtures — shared across scoring tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="session")
def reviewer_cases() -> list[dict[str, Any]]:
    """All reviewer eval cases, each a (lab_state, aim, ground truth) triple."""
    path = Path(__file__).parent / "fixtures" / "cases.json"
    data = json.loads(path.read_text())
    return list(data["cases"])
