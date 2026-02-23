"""Compression ratio tests for distillation engine."""

import json
from typing import Any

import pytest
import tiktoken


def count_tokens(data: dict[str, Any]) -> int:
    """Count tokens in JSON-serialized data."""
    text = json.dumps(data)
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


MAX_TOKENS = 2000


@pytest.mark.compression
class TestCompressionRatio:
    """Test that lab states stay within token budget."""

    def test_genomics_lab_within_budget(self, genomics_lab: dict[str, Any]) -> None:
        """Genomics lab state should be under 2K tokens."""
        state = genomics_lab["ground_truth"]
        token_count = count_tokens(state)

        assert token_count < MAX_TOKENS, (
            f"Genomics lab state exceeds token budget: {token_count} > {MAX_TOKENS}"
        )

    def test_protein_lab_within_budget(self, protein_lab: dict[str, Any]) -> None:
        """Protein lab state should be under 2K tokens."""
        state = protein_lab["ground_truth"]
        token_count = count_tokens(state)

        assert token_count < MAX_TOKENS, (
            f"Protein lab state exceeds token budget: {token_count} > {MAX_TOKENS}"
        )

    def test_cell_bio_lab_within_budget(self, cell_bio_lab: dict[str, Any]) -> None:
        """Cell bio lab state should be under 2K tokens."""
        state = cell_bio_lab["ground_truth"]
        token_count = count_tokens(state)

        assert token_count < MAX_TOKENS, (
            f"Cell bio lab state exceeds token budget: {token_count} > {MAX_TOKENS}"
        )

    def test_empty_state_minimal(self, empty_state: dict[str, Any]) -> None:
        """Empty state should use minimal tokens."""
        token_count = count_tokens(empty_state)

        # Empty state should be very small
        assert token_count < 100, (
            f"Empty state uses too many tokens: {token_count}"
        )


@pytest.mark.compression
class TestStateStructure:
    """Test that lab states have required structure."""

    REQUIRED_KEYS = [
        "equipment",
        "techniques",
        "expertise",
        "organisms",
        "reagents",
        "experimental_history",
        "resource_constraints",
        "signal_count",
    ]

    def test_genomics_lab_structure(self, genomics_lab: dict[str, Any]) -> None:
        """Genomics lab state should have all required keys."""
        state = genomics_lab["ground_truth"]

        for key in self.REQUIRED_KEYS:
            assert key in state, f"Missing required key: {key}"

    def test_protein_lab_structure(self, protein_lab: dict[str, Any]) -> None:
        """Protein lab state should have all required keys."""
        state = protein_lab["ground_truth"]

        for key in self.REQUIRED_KEYS:
            assert key in state, f"Missing required key: {key}"

    def test_cell_bio_lab_structure(self, cell_bio_lab: dict[str, Any]) -> None:
        """Cell bio lab state should have all required keys."""
        state = cell_bio_lab["ground_truth"]

        for key in self.REQUIRED_KEYS:
            assert key in state, f"Missing required key: {key}"

    def test_equipment_has_required_fields(self, genomics_lab: dict[str, Any]) -> None:
        """Equipment items should have name and capabilities."""
        state = genomics_lab["ground_truth"]

        for equipment in state["equipment"]:
            assert "name" in equipment, "Equipment missing name"
            assert "capabilities" in equipment, "Equipment missing capabilities"
            assert isinstance(equipment["capabilities"], list), "Capabilities should be a list"

    def test_techniques_have_proficiency(self, genomics_lab: dict[str, Any]) -> None:
        """Techniques should have proficiency level."""
        state = genomics_lab["ground_truth"]

        for technique in state["techniques"]:
            assert "name" in technique, "Technique missing name"
            assert "proficiency" in technique, "Technique missing proficiency"
            assert technique["proficiency"] in ["expert", "competent", "learning"], (
                f"Invalid proficiency: {technique['proficiency']}"
            )
