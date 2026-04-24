"""Multi-turn reviewer eval — runs the full agent loop against fixture cases.

Scores three axes per case: grounding (used tools), coverage (hits the
intended gaps/strengths), actionability (final answer contains a concrete
next step). Target: ≥7/10 on each axis.

Requires `ANTHROPIC_API_KEY` — skipped in CI runs without the key.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

pytest.importorskip("litellm")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import EvalScore, run_case  # type: ignore[import-not-found]  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Reviewer eval needs ANTHROPIC_API_KEY (skipped in unit-test CI).",
)

DEFAULT_MODEL = os.environ.get("REVIEWER_EVAL_MODEL", "claude-sonnet-4-6")
AXIS_TARGET = 7  # out of 10 cases


@pytest.fixture(scope="module")
async def scored_cases(reviewer_cases: list[dict[str, Any]]) -> list[EvalScore]:
    """Run every case exactly once and reuse the scores across axis tests."""
    results: list[EvalScore] = []
    for case in reviewer_cases:
        score = await run_case(case, model=DEFAULT_MODEL)
        results.append(score)
    return results


def _fail_report(axis: str, scores: list[EvalScore]) -> str:
    lines = [f"{axis} axis pass rate below target:"]
    for s in scores:
        flag = "PASS" if getattr(s, axis) else "FAIL"
        lines.append(f"  {flag} {s.case_id} — {s.notes}")
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_grounding_pass_rate(scored_cases: list[EvalScore]) -> None:
    passed = sum(1 for s in scored_cases if s.grounding)
    assert passed >= AXIS_TARGET, _fail_report("grounding", scored_cases)


@pytest.mark.asyncio
async def test_coverage_pass_rate(scored_cases: list[EvalScore]) -> None:
    passed = sum(1 for s in scored_cases if s.coverage)
    assert passed >= AXIS_TARGET, _fail_report("coverage", scored_cases)


@pytest.mark.asyncio
async def test_actionability_pass_rate(scored_cases: list[EvalScore]) -> None:
    passed = sum(1 for s in scored_cases if s.actionability)
    assert passed >= AXIS_TARGET, _fail_report("actionability", scored_cases)
