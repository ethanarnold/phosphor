"""Prompt loader sanity checks."""

from __future__ import annotations

import pytest

from app.agents.prompts import load_prompt


def test_load_prompt_reads_reviewer_template() -> None:
    content = load_prompt("reviewer")
    assert "Reviewer #2" in content
    # Key workflow beats the model must see.
    assert "get_lab_state" in content
    assert "What's grounded" in content
    assert "What's missing" in content
    assert "concrete next step" in content


def test_load_prompt_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")
