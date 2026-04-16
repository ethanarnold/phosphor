"""Shared fixtures for extraction eval harness."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def extraction_fixtures_path() -> Path:
    """Path to extraction fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def biology_abstracts(extraction_fixtures_path: Path) -> list[dict[str, Any]]:
    """Biology abstracts with expected opportunities."""
    return json.loads((extraction_fixtures_path / "biology_abstracts.json").read_text())


@pytest.fixture
def chemistry_abstracts(extraction_fixtures_path: Path) -> list[dict[str, Any]]:
    """Chemistry abstracts with expected opportunities."""
    return json.loads((extraction_fixtures_path / "chemistry_abstracts.json").read_text())


@pytest.fixture
def physics_abstracts(extraction_fixtures_path: Path) -> list[dict[str, Any]]:
    """Physics abstracts with expected opportunities."""
    return json.loads((extraction_fixtures_path / "physics_abstracts.json").read_text())


@pytest.fixture
def edge_cases(extraction_fixtures_path: Path) -> list[dict[str, Any]]:
    """Edge case abstracts (vague, multi-domain, retracted, etc.)."""
    return json.loads((extraction_fixtures_path / "edge_cases.json").read_text())


@pytest.fixture
def all_abstracts(
    biology_abstracts: list[dict[str, Any]],
    chemistry_abstracts: list[dict[str, Any]],
    physics_abstracts: list[dict[str, Any]],
    edge_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """All abstracts combined."""
    return biology_abstracts + chemistry_abstracts + physics_abstracts + edge_cases
