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


def test_load_prompt_reads_directions_template() -> None:
    content = load_prompt("directions")
    # Workflow signals the model must see.
    assert "get_lab_state" in content
    assert "search_literature" in content
    # Output discipline beats.
    assert "Headline" in content
    assert "First experiment" in content
    assert "Feasibility flag" in content


def test_load_prompt_reads_strengthen_template() -> None:
    content = load_prompt("strengthen")
    assert "get_lab_state" in content
    assert "search_experiments" in content
    assert "search_literature" in content
    assert "What to do" in content
    assert "What it tells you" in content
    assert "Which blocker it addresses" in content
