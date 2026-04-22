"""Unit tests for the experiments service — quick-log LLM parsing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.experiments import _strip_code_fence, parse_quick_log

FENCED_JSON = (
    '```json\n'
    '{\n'
    '  "technique": "Western blot",\n'
    '  "outcome": "partial",\n'
    '  "notes": "faint bands",\n'
    '  "equipment_used": [],\n'
    '  "organisms_used": ["HeLa"],\n'
    '  "reagents_used": []\n'
    '}\n'
    '```'
)
BARE_JSON = '{"technique": "qPCR", "outcome": "success", "notes": "clean amplification"}'


def _canned(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _settings():  # type: ignore[no-untyped-def]
    return SimpleNamespace(llm_model="claude-sonnet-4-6")


def test_strip_code_fence_removes_json_fence() -> None:
    assert '"technique": "Western blot"' in _strip_code_fence(FENCED_JSON)
    assert not _strip_code_fence(FENCED_JSON).startswith("```")


def test_strip_code_fence_passthrough_for_bare_json() -> None:
    assert _strip_code_fence(BARE_JSON) == BARE_JSON


def test_strip_code_fence_handles_plain_fence_without_lang() -> None:
    raw = "```\n" + BARE_JSON + "\n```"
    assert _strip_code_fence(raw) == BARE_JSON


@pytest.mark.asyncio
async def test_parse_quick_log_parses_fenced_output() -> None:
    with patch(
        "app.services.experiments.acompletion",
        new=AsyncMock(return_value=_canned(FENCED_JSON)),
    ):
        entry = await parse_quick_log(
            text="ran Western blot, faint bands",
            outcome_hint=None,
            settings=_settings(),
        )
    assert entry.technique == "Western blot"
    assert entry.outcome == "partial"


@pytest.mark.asyncio
async def test_parse_quick_log_parses_bare_json() -> None:
    with patch(
        "app.services.experiments.acompletion",
        new=AsyncMock(return_value=_canned(BARE_JSON)),
    ):
        entry = await parse_quick_log(
            text="ran qPCR, clean amplification",
            outcome_hint=None,
            settings=_settings(),
        )
    assert entry.technique == "qPCR"
    assert entry.outcome == "success"
