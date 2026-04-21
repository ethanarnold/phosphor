"""Shared fixtures for matching eval harness."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def matching_fixtures_path() -> Path:
    """Path to matching fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def genomics_scenario(matching_fixtures_path: Path) -> dict[str, Any]:
    """Genomics lab + opportunities + expected ranking."""
    return json.loads((matching_fixtures_path / "genomics_scenario.json").read_text())


@pytest.fixture
def chemistry_scenario(matching_fixtures_path: Path) -> dict[str, Any]:
    """Chemistry lab + opportunities + expected ranking."""
    return json.loads((matching_fixtures_path / "chemistry_scenario.json").read_text())


@pytest.fixture
def edge_cases(matching_fixtures_path: Path) -> dict[str, Any]:
    """Edge cases (full-match, no-match, sparse lab state)."""
    return json.loads((matching_fixtures_path / "edge_cases.json").read_text())


@pytest.fixture
def all_scenarios(
    genomics_scenario: dict[str, Any],
    chemistry_scenario: dict[str, Any],
    edge_cases: dict[str, Any],
) -> list[dict[str, Any]]:
    """Combined list of all ranking scenarios."""
    return [genomics_scenario, chemistry_scenario, edge_cases]
