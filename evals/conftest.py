"""Shared fixtures for eval harness."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def fixtures_path() -> Path:
    """Path to fixtures directory."""
    return Path(__file__).parent / "distillation" / "fixtures"


@pytest.fixture
def genomics_lab(fixtures_path: Path) -> dict[str, Any]:
    """Genomics lab ground truth fixture."""
    return json.loads((fixtures_path / "genomics_lab.json").read_text())


@pytest.fixture
def protein_lab(fixtures_path: Path) -> dict[str, Any]:
    """Protein lab ground truth fixture."""
    return json.loads((fixtures_path / "protein_lab.json").read_text())


@pytest.fixture
def cell_bio_lab(fixtures_path: Path) -> dict[str, Any]:
    """Cell biology lab ground truth fixture."""
    return json.loads((fixtures_path / "cell_bio_lab.json").read_text())


@pytest.fixture
def empty_state() -> dict[str, Any]:
    """Empty lab state."""
    return {
        "equipment": [],
        "techniques": [],
        "expertise": [],
        "organisms": [],
        "reagents": [],
        "experimental_history": [],
        "resource_constraints": {},
        "signal_count": 0,
    }
