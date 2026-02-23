"""Fidelity tests - can LLM answer questions about lab state accurately?"""

import json
import os
from typing import Any

import pytest
from litellm import acompletion

# Skip fidelity tests if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)


async def ask_question_about_state(
    state: dict[str, Any],
    question: str,
) -> str:
    """Ask LLM a question about the lab state and get answer."""
    prompt = f"""Given the following lab state information, answer the question.
Answer concisely with just the key information requested.
If the information is not available or the capability is not present, say "no" or "not specified".

Lab State:
{json.dumps(state, indent=2)}

Question: {question}

Answer:"""

    response = await acompletion(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=100,
    )

    return response.choices[0].message.content.strip().lower()


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    answer = answer.lower().strip()

    # Map common variations
    if answer in ["yes", "true", "correct", "available", "they can", "yes,"]:
        return "yes"
    if answer in ["no", "false", "not available", "they cannot", "no,", "not specified"]:
        return "no"

    return answer


@pytest.mark.fidelity
@pytest.mark.asyncio
class TestFidelityQA:
    """Test that LLM can accurately answer questions about lab states."""

    async def test_genomics_lab_qa(self, genomics_lab: dict[str, Any]) -> None:
        """Test QA accuracy on genomics lab."""
        state = genomics_lab["ground_truth"]
        qa_pairs = genomics_lab["qa_pairs"]

        correct = 0
        total = len(qa_pairs)

        for qa in qa_pairs:
            answer = await ask_question_about_state(state, qa["question"])
            normalized = normalize_answer(answer)
            expected = qa["expected"].lower()

            # Check if answer contains expected value
            if expected in normalized or normalized in expected:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.8, (
            f"Genomics lab QA accuracy too low: {accuracy:.0%} ({correct}/{total})"
        )

    async def test_protein_lab_qa(self, protein_lab: dict[str, Any]) -> None:
        """Test QA accuracy on protein lab."""
        state = protein_lab["ground_truth"]
        qa_pairs = protein_lab["qa_pairs"]

        correct = 0
        total = len(qa_pairs)

        for qa in qa_pairs:
            answer = await ask_question_about_state(state, qa["question"])
            normalized = normalize_answer(answer)
            expected = qa["expected"].lower()

            if expected in normalized or normalized in expected:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.8, (
            f"Protein lab QA accuracy too low: {accuracy:.0%} ({correct}/{total})"
        )

    async def test_cell_bio_lab_qa(self, cell_bio_lab: dict[str, Any]) -> None:
        """Test QA accuracy on cell bio lab."""
        state = cell_bio_lab["ground_truth"]
        qa_pairs = cell_bio_lab["qa_pairs"]

        correct = 0
        total = len(qa_pairs)

        for qa in qa_pairs:
            answer = await ask_question_about_state(state, qa["question"])
            normalized = normalize_answer(answer)
            expected = qa["expected"].lower()

            if expected in normalized or normalized in expected:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.8, (
            f"Cell bio lab QA accuracy too low: {accuracy:.0%} ({correct}/{total})"
        )


@pytest.mark.fidelity
@pytest.mark.asyncio
class TestNegativeCapabilities:
    """Test that LLM correctly identifies missing capabilities."""

    async def test_genomics_lab_no_flow_cytometry(
        self, genomics_lab: dict[str, Any]
    ) -> None:
        """Genomics lab should not claim to have flow cytometry."""
        state = genomics_lab["ground_truth"]
        answer = await ask_question_about_state(
            state, "Does this lab have flow cytometry capability?"
        )

        assert "no" in answer.lower() or "not" in answer.lower(), (
            f"Incorrectly claimed flow cytometry capability: {answer}"
        )

    async def test_protein_lab_no_cryoem(self, protein_lab: dict[str, Any]) -> None:
        """Protein lab should not claim to have cryo-EM."""
        state = protein_lab["ground_truth"]
        answer = await ask_question_about_state(
            state, "Can they do cryo-EM?"
        )

        assert "no" in answer.lower() or "not" in answer.lower(), (
            f"Incorrectly claimed cryo-EM capability: {answer}"
        )
