"""Field coverage tests - extraction works across domains."""

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


@pytest.mark.extraction
@pytest.mark.asyncio
class TestFieldCoverage:
    """Test that extraction works across scientific domains."""

    async def test_biology_coverage(
        self, biology_abstracts: list[dict[str, Any]]
    ) -> None:
        """At least 60% of biology abstracts with expected opportunities should yield extractions."""
        concrete = [a for a in biology_abstracts if not a.get("expected_none")]
        produced = 0

        for abstract_data in concrete:
            extracted = await extract_from_abstract(abstract_data)
            if extracted:
                produced += 1

        coverage = produced / len(concrete) if concrete else 0
        assert coverage >= 0.60, (
            f"Biology coverage too low: {coverage:.0%} ({produced}/{len(concrete)})"
        )

    async def test_chemistry_coverage(
        self, chemistry_abstracts: list[dict[str, Any]]
    ) -> None:
        """At least 60% of chemistry abstracts with expected opportunities should yield extractions."""
        concrete = [a for a in chemistry_abstracts if not a.get("expected_none")]
        produced = 0

        for abstract_data in concrete:
            extracted = await extract_from_abstract(abstract_data)
            if extracted:
                produced += 1

        coverage = produced / len(concrete) if concrete else 0
        assert coverage >= 0.60, (
            f"Chemistry coverage too low: {coverage:.0%} ({produced}/{len(concrete)})"
        )

    async def test_physics_coverage(
        self, physics_abstracts: list[dict[str, Any]]
    ) -> None:
        """At least 60% of physics abstracts with expected opportunities should yield extractions."""
        concrete = [a for a in physics_abstracts if not a.get("expected_none")]
        produced = 0

        for abstract_data in concrete:
            extracted = await extract_from_abstract(abstract_data)
            if extracted:
                produced += 1

        coverage = produced / len(concrete) if concrete else 0
        assert coverage >= 0.60, (
            f"Physics coverage too low: {coverage:.0%} ({produced}/{len(concrete)})"
        )

    async def test_no_domain_dramatically_worse(
        self,
        biology_abstracts: list[dict[str, Any]],
        chemistry_abstracts: list[dict[str, Any]],
        physics_abstracts: list[dict[str, Any]],
    ) -> None:
        """No single domain should have dramatically lower coverage than others."""
        coverages: dict[str, float] = {}

        for domain, abstracts in [
            ("biology", biology_abstracts),
            ("chemistry", chemistry_abstracts),
            ("physics", physics_abstracts),
        ]:
            concrete = [a for a in abstracts if not a.get("expected_none")]
            produced = 0
            for abstract_data in concrete:
                extracted = await extract_from_abstract(abstract_data)
                if extracted:
                    produced += 1
            coverages[domain] = produced / len(concrete) if concrete else 0

        max_coverage = max(coverages.values())
        min_coverage = min(coverages.values())

        assert max_coverage - min_coverage < 0.30, (
            f"Coverage gap too large: {coverages} "
            f"(max-min = {max_coverage - min_coverage:.2f})"
        )
