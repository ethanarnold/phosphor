"""Gap detection eval — does analyze_gaps surface the known missing items?

Like the ranking test, this runs offline: no LLM, no DB. The matching service's
`analyze_gaps` needs an AsyncSession + ORM rows, so we reach into the
underlying `score_*` helpers directly with the scenario's raw dict data.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

# Matching service imports sqlalchemy; skip entire module if the lightweight
# evals venv doesn't have backend runtime deps installed.
pytest.importorskip("sqlalchemy")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.schemas.lab_state import LabStateData  # noqa: E402
from app.services.matching import (  # noqa: E402
    score_equipment,
    score_expertise,
)


def _missing(scenario: dict[str, Any], opp_id: str) -> tuple[list[str], list[str]]:
    """Return (missing_equipment, expertise_gaps) for one opportunity."""
    lab_state = LabStateData.model_validate(scenario["lab_state"])
    opp = next(o for o in scenario["opportunities"] if o["id"] == opp_id)
    eq = score_equipment(lab_state, opp.get("required_equipment", []))
    exp = score_expertise(lab_state, opp.get("required_expertise", []))
    missing_equipment = [k for k, v in eq.items() if v == "cannot"]
    expertise_gaps = [k for k, v in exp.items() if v == "gap"]
    return missing_equipment, expertise_gaps


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum() or c.isspace()).strip()


def _hits(predicted: list[str], expected: list[str]) -> int:
    """Count how many expected items appear (fuzzy) in predicted."""
    pred_norm = [_norm(p) for p in predicted]
    count = 0
    for exp in expected:
        en = _norm(exp)
        if any(en in p or p in en for p in pred_norm):
            count += 1
    return count


@pytest.mark.matching
class TestGapDetection:
    """Known gaps from scenario fixtures must be surfaced by gap analysis."""

    def _check_scenario(self, scenario: dict[str, Any]) -> None:
        known_gaps = scenario.get("known_gaps", {})
        total_expected = 0
        total_hit = 0
        for opp_id, gaps in known_gaps.items():
            missing_equipment, expertise_gaps = _missing(scenario, opp_id)

            exp_missing_eq = gaps.get("missing_equipment", [])
            total_expected += len(exp_missing_eq)
            total_hit += _hits(missing_equipment, exp_missing_eq)

            exp_missing_exp = gaps.get("expertise_gaps", [])
            total_expected += len(exp_missing_exp)
            total_hit += _hits(expertise_gaps, exp_missing_exp)

        if total_expected == 0:
            return
        recall = total_hit / total_expected
        assert recall >= 0.9, (
            f"Gap detection recall too low: {recall:.2f} "
            f"({total_hit}/{total_expected} in {scenario.get('name', '?')})"
        )

    def test_genomics(self, genomics_scenario: dict[str, Any]) -> None:
        self._check_scenario(genomics_scenario)

    def test_chemistry(self, chemistry_scenario: dict[str, Any]) -> None:
        self._check_scenario(chemistry_scenario)

    def test_edge_cases(self, edge_cases: dict[str, Any]) -> None:
        self._check_scenario(edge_cases)
