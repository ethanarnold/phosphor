"""Quality scoring tests for extracted opportunities."""

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
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


@pytest.mark.extraction
@pytest.mark.asyncio
class TestQualityScoring:
    """Test that extracted opportunities meet quality standards."""

    async def test_description_length(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """All extracted opportunity descriptions should be >= 50 chars."""
        concrete_abstracts = [a for a in all_abstracts if not a.get("expected_none")]
        short_descriptions = 0
        total_opps = 0

        for abstract_data in concrete_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            for opp in extracted:
                total_opps += 1
                if len(opp.get("description", "")) < 50:
                    short_descriptions += 1

        if total_opps > 0:
            short_rate = short_descriptions / total_opps
            assert short_rate < 0.1, (
                f"Too many short descriptions: {short_descriptions}/{total_opps} "
                f"({short_rate:.0%})"
            )

    async def test_resource_requirements_present(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """Each opportunity should have at least one resource requirement."""
        concrete_abstracts = [a for a in all_abstracts if not a.get("expected_none")]
        missing_resources = 0
        total_opps = 0

        for abstract_data in concrete_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            for opp in extracted:
                total_opps += 1
                has_equipment = bool(opp.get("required_equipment"))
                has_techniques = bool(opp.get("required_techniques"))
                has_expertise = bool(opp.get("required_expertise"))

                if not (has_equipment or has_techniques or has_expertise):
                    missing_resources += 1

        if total_opps > 0:
            missing_rate = missing_resources / total_opps
            assert missing_rate < 0.1, (
                f"Too many opportunities without resource requirements: "
                f"{missing_resources}/{total_opps} ({missing_rate:.0%})"
            )

    async def test_valid_complexity_values(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """All complexity values should be valid."""
        valid_values = {"low", "medium", "high"}
        concrete_abstracts = [a for a in all_abstracts if not a.get("expected_none")]
        invalid_count = 0
        total_opps = 0

        for abstract_data in concrete_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            for opp in extracted:
                total_opps += 1
                if opp.get("estimated_complexity") not in valid_values:
                    invalid_count += 1

        if total_opps > 0:
            assert invalid_count == 0, (
                f"{invalid_count}/{total_opps} opportunities have invalid complexity values"
            )

    async def test_mean_quality_score(
        self, all_abstracts: list[dict[str, Any]]
    ) -> None:
        """Mean concreteness score across all extractions should be >= 0.6."""
        concrete_abstracts = [a for a in all_abstracts if not a.get("expected_none")]
        scores: list[float] = []

        for abstract_data in concrete_abstracts:
            extracted = await extract_from_abstract(abstract_data)
            for opp in extracted:
                score = opp.get("concreteness_score", 0.0)
                if isinstance(score, (int, float)):
                    scores.append(float(score))

        if scores:
            mean_score = sum(scores) / len(scores)
            assert mean_score >= 0.6, (
                f"Mean quality score too low: {mean_score:.2f} "
                f"(from {len(scores)} opportunities)"
            )
