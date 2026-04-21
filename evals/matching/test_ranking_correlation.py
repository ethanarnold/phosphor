"""Ranking correlation eval — does the matching engine rank opportunities
in the same order a human evaluator would?

The matching scorer is pure Python, so this runs offline (no LLM, no DB).
Alignment is held neutral (0.5) so feasibility is what's being measured.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Matching service imports sqlalchemy; skip entire module if the lightweight
# evals venv doesn't have backend runtime deps installed.
pytest.importorskip("sqlalchemy")

# Make backend.app importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.schemas.lab_state import LabStateData  # noqa: E402
from app.services.matching import build_match_score  # noqa: E402


def _spearman(predicted: list[str], expected: list[str]) -> float:
    """Spearman rank correlation between two orderings of the same items."""
    ranks_pred = {item: i for i, item in enumerate(predicted)}
    ranks_exp = {item: i for i, item in enumerate(expected)}
    common = list(set(ranks_pred) & set(ranks_exp))
    n = len(common)
    if n < 2:
        return 1.0
    d_sum = sum((ranks_pred[k] - ranks_exp[k]) ** 2 for k in common)
    return 1 - (6 * d_sum) / (n * (n**2 - 1))


def _predicted_order(scenario: dict[str, Any]) -> list[str]:
    lab_state = LabStateData.model_validate(scenario["lab_state"])
    scored: list[tuple[str, float]] = []
    for raw_opp in scenario["opportunities"]:
        stub = SimpleNamespace(
            required_equipment=raw_opp.get("required_equipment", []),
            required_techniques=raw_opp.get("required_techniques", []),
            required_expertise=raw_opp.get("required_expertise", []),
        )
        score = build_match_score(lab_state, stub, alignment=0.5)  # type: ignore[arg-type]
        scored.append((raw_opp["id"], score.composite))
    scored.sort(key=lambda p: p[1], reverse=True)
    return [opp_id for opp_id, _ in scored]


@pytest.mark.matching
class TestRankingCorrelation:
    """Matching engine should correlate with expert-annotated rankings."""

    def test_genomics(self, genomics_scenario: dict[str, Any]) -> None:
        predicted = _predicted_order(genomics_scenario)
        expected = genomics_scenario["expected_ranking"]
        rho = _spearman(predicted, expected)
        assert rho >= 0.7, (
            f"Spearman ρ too low: {rho:.2f} "
            f"(predicted={predicted}, expected={expected})"
        )

    def test_chemistry(self, chemistry_scenario: dict[str, Any]) -> None:
        predicted = _predicted_order(chemistry_scenario)
        expected = chemistry_scenario["expected_ranking"]
        rho = _spearman(predicted, expected)
        assert rho >= 0.7, (
            f"Spearman ρ too low: {rho:.2f} "
            f"(predicted={predicted}, expected={expected})"
        )

    def test_edge_cases(self, edge_cases: dict[str, Any]) -> None:
        predicted = _predicted_order(edge_cases)
        expected = edge_cases["expected_ranking"]
        rho = _spearman(predicted, expected)
        assert rho >= 0.7, (
            f"Spearman ρ too low: {rho:.2f} "
            f"(predicted={predicted}, expected={expected})"
        )

    def test_full_match_ranks_first_in_edge_cases(
        self, edge_cases: dict[str, Any]
    ) -> None:
        predicted = _predicted_order(edge_cases)
        assert predicted[0] == "opp_full_match"

    def test_zero_match_ranks_last_in_edge_cases(
        self, edge_cases: dict[str, Any]
    ) -> None:
        predicted = _predicted_order(edge_cases)
        assert predicted[-1] == "opp_zero_match"
