"""Precision and recall tests for opportunity extraction."""

import json
import os
from typing import Any

import pytest
from litellm import acompletion

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

EXTRACTION_SYSTEM_PROMPT = """You are a research opportunity extractor. Given scientific paper abstracts, identify concrete, actionable research opportunities.

Rules:
1. EXTRACT only concrete opportunities with identifiable resource requirements
2. REJECT vague statements like "more research is needed" or "future work should explore"
3. Each opportunity MUST specify at least one of: required_equipment, required_techniques, or required_expertise
4. Rate estimated_complexity based on resource requirements and novelty
5. Rate concreteness_score from 0.0 to 1.0 (how actionable and specific the opportunity is)
6. If NO concrete opportunities exist in the abstracts, return an empty array []

Output ONLY a valid JSON array. No markdown, no explanation.

Schema for each opportunity:
{
  "description": "Detailed description of the research opportunity (50+ chars)",
  "required_equipment": ["list of equipment needed"],
  "required_techniques": ["list of techniques needed"],
  "required_expertise": ["list of expertise areas needed"],
  "estimated_complexity": "low" | "medium" | "high",
  "concreteness_score": 0.0-1.0,
  "source_paper_indices": [0]
}"""


async def extract_from_abstract(abstract_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Run extraction on a single abstract."""
    user_prompt = f"""Extract concrete research opportunities from this abstract:

Paper 0:
Title: {abstract_data['title']}
Abstract: {abstract_data['abstract']}

Output a JSON array of opportunities (or empty array if none found):"""

    response = await acompletion(
        model="claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=2000,
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [o for o in result if o.get("concreteness_score", 0) >= 0.5]
        return []
    except json.JSONDecodeError:
        return []


def opportunities_match(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Compare extracted opportunities against expected.

    Returns:
        (true_positives, false_positives, false_negatives)
    """
    matched_expected: set[int] = set()

    for ext_opp in extracted:
        ext_desc = ext_opp.get("description", "").lower()
        ext_equip = " ".join(ext_opp.get("required_equipment", [])).lower()
        ext_all = ext_desc + " " + ext_equip

        best_match = -1
        best_score = 0

        for j, exp_opp in enumerate(expected):
            if j in matched_expected:
                continue

            # Check keyword overlap
            desc_keywords = exp_opp.get("description_keywords", [])
            equip_keywords = exp_opp.get("required_equipment_keywords", [])

            desc_matches = sum(1 for kw in desc_keywords if kw.lower() in ext_all)
            equip_matches = sum(1 for kw in equip_keywords if kw.lower() in ext_all)

            total_keywords = len(desc_keywords) + len(equip_keywords)
            if total_keywords == 0:
                continue

            score = (desc_matches + equip_matches) / total_keywords

            if score > best_score and score >= 0.3:  # 30% keyword overlap threshold
                best_score = score
                best_match = j

        if best_match >= 0:
            matched_expected.add(best_match)

    tp = len(matched_expected)
    fp = len(extracted) - tp
    fn = len(expected) - tp

    return tp, fp, fn


@pytest.mark.extraction
@pytest.mark.asyncio
class TestPrecisionRecall:
    """Test extraction precision and recall across all abstracts."""

    async def test_overall_precision_recall(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """Test aggregate precision and recall across all domains."""
        total_tp = 0
        total_fp = 0
        total_fn = 0

        for abstract_data in all_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            expected = abstract_data.get("expected_opportunities", [])

            if abstract_data.get("expected_none", False):
                # For "none" cases, any extraction is a false positive
                total_fp += len(extracted)
            else:
                tp, fp, fn = opportunities_match(extracted, expected)
                total_tp += tp
                total_fp += fp
                total_fn += fn

        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0

        assert precision >= 0.75, (
            f"Precision too low: {precision:.2f} "
            f"(TP={total_tp}, FP={total_fp}, FN={total_fn})"
        )
        assert recall >= 0.70, (
            f"Recall too low: {recall:.2f} "
            f"(TP={total_tp}, FP={total_fp}, FN={total_fn})"
        )

    async def test_false_positive_rate_on_none_abstracts(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """Abstracts with no opportunities should produce zero or near-zero extractions."""
        none_abstracts = [a for a in all_abstracts if a.get("expected_none", False)]
        total_false_positives = 0

        for abstract_data in none_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            total_false_positives += len(extracted)

        fp_rate = total_false_positives / len(none_abstracts) if none_abstracts else 0

        assert fp_rate < 0.2, (
            f"False positive rate too high on none-abstracts: {fp_rate:.2f} "
            f"({total_false_positives} extractions from {len(none_abstracts)} abstracts)"
        )
