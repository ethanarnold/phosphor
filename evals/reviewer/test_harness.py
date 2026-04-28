"""Offline harness smoke tests.

Uses a scripted completion to exercise the harness scoring logic without
an LLM. Every CI run exercises these; the full reviewer eval above only
runs when ANTHROPIC_API_KEY is available.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

pytest.importorskip("litellm")

from app.agents.loop import run_agent  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import (  # type: ignore[import-not-found]  # noqa: E402
    _build_fixture_registry,
    _score_actionability,
    _score_coverage,
    _score_grounding,
)


def _fn_call(name: str, args: dict[str, Any], call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _resp(content: str | None, tool_calls: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls or None)
            )
        ]
    )


def _scripted(responses: list[SimpleNamespace]):  # noqa: ANN202
    queue = list(responses)

    async def _call(**_: Any) -> SimpleNamespace:
        return queue.pop(0)

    return _call


def test_fixtures_file_is_readable_and_has_ten_cases() -> None:
    path = Path(__file__).parent / "fixtures" / "cases.json"
    cases = json.loads(path.read_text())["cases"]
    assert len(cases) == 10
    for c in cases:
        assert {"id", "lab_state", "aim"} <= set(c.keys())


def test_fixture_registry_validates_state_against_real_schema(
    reviewer_cases: list[dict[str, Any]],
) -> None:
    """If a fixture's lab_state drifted from LabStateData, build would raise."""
    for case in reviewer_cases:
        _build_fixture_registry(case["lab_state"])


@pytest.mark.asyncio
async def test_registry_search_returns_expected_matches(
    reviewer_cases: list[dict[str, Any]],
) -> None:
    case = next(c for c in reviewer_cases if c["id"] == "microglia_crispri_trem2")
    registry = _build_fixture_registry(case["lab_state"])
    hits = await registry.dispatch("search_experiments", {"query": "CRISPR"})
    assert any("CRISPR" in m["snippet"] for m in hits["matches"])


@pytest.mark.asyncio
async def test_harness_scores_a_strong_run_as_pass(
    reviewer_cases: list[dict[str, Any]],
) -> None:
    """Scripted run that calls tools and produces a well-formed critique
    should pass all three axes."""
    case = next(c for c in reviewer_cases if c["id"] == "microglia_crispri_trem2")
    registry = _build_fixture_registry(case["lab_state"])

    completion = _scripted(
        [
            _resp(None, [_fn_call("get_lab_state", {}, "a")]),
            _resp(None, [_fn_call("search_experiments", {"query": "CRISPR"}, "b")]),
            _resp(None, [_fn_call("search_experiments", {"query": "primary microglia"}, "c")]),
            _resp(
                "What's grounded: CRISPR knockouts done 7× in HEK293/K562. Bulk RNA-seq "
                "is established. Immunocytochemistry is competent.\n\n"
                "What's missing: no primary human microglia, no CRISPRi (only knockouts), "
                "no single-cell pipeline.\n\n"
                "Concrete next step: collaborate with a microglia lab, or spend 3 months "
                "on primary microglia method development first."
            ),
        ]
    )
    result = await run_agent(
        system_prompt="sys",
        user_message=case["aim"],
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )
    assert _score_grounding(result) is True
    assert _score_coverage(result, case) is True
    assert _score_actionability(result, case) is True


@pytest.mark.asyncio
async def test_harness_scores_a_hallucinated_run_as_fail(
    reviewer_cases: list[dict[str, Any]],
) -> None:
    """A run with no tool calls must fail the grounding axis."""
    case = next(c for c in reviewer_cases if c["id"] == "microglia_crispri_trem2")
    registry = _build_fixture_registry(case["lab_state"])

    completion = _scripted(
        [_resp("The lab obviously can do this, proceed as planned.", None)]
    )
    result = await run_agent(
        system_prompt="sys",
        user_message=case["aim"],
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )
    assert _score_grounding(result) is False
    # Coverage fails because no intended gaps are flagged.
    assert _score_coverage(result, case) is False
    # Actionability fails for the same absence.
    assert _score_actionability(result, case) is False
