"""Precision/recall eval for the publication-import capability extractor.

Runs the LLM end-to-end against a small hand-labeled fixture set and asserts
recall and precision floors. The eval is self-contained — it inlines the
system prompt rather than importing from `backend/app/`, so the lightweight
evals environment doesn't need the full backend dependency tree.

Skipped automatically when ``ANTHROPIC_API_KEY`` is unset.

Aggregation correctness (canonical names, alias map, source dedup) lives in
the unit-test suite under `backend/tests/test_capability_extraction.py` —
keep it there because it's pure-Python and runs on every PR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from litellm import acompletion

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "capability_papers.json"

# Inlined verbatim from `backend/app/agents/prompts/capability_extraction.md`.
# If you change the prompt, update both files. The mismatch tells you the
# eval has drifted from production.
CAPABILITY_EXTRACTION_PROMPT = """You are a lab capability extractor. Given the title, abstract, MeSH terms, and publication year of a single scientific paper authored or co-authored by a lab member, extract the concrete laboratory capabilities the paper demonstrates the lab has used.

The output drives a lab-state matching engine. Garbage in poisons matching for months — bias toward precision over recall.

## What to extract

Five categories. Each entry needs a `name` (short canonical phrase) and an `evidence` field containing a brief quote or paraphrase from the abstract that justifies the entry.

- **techniques**: experimental or computational methods the lab actually performed (e.g. "CRISPR-Cas9 knockout", "patch-clamp electrophysiology", "single-cell RNA-seq", "molecular dynamics simulation"). Include the technique even if it's a generic protocol; specificity is preferred when the abstract supports it.
- **organisms**: model systems used or studied (e.g. "Mus musculus", "Saccharomyces cerevisiae", "HeLa cells", "Drosophila melanogaster", "primary human hepatocytes"). Include cell lines.
- **equipment**: instruments named directly OR strongly implied by a uniquely named technique (e.g. cryo-EM technique → "cryo-electron microscope"; LC-MS/MS technique → "LC-MS/MS instrument"; nanopore sequencing → "Oxford Nanopore sequencer"). Skip generic items like "pipettes" or "incubator".
- **reagents**: distinctive antibodies, plasmids, small molecules, kits named in the abstract (e.g. "anti-CD8 monoclonal antibody", "olaparib", "10x Genomics Chromium kit"). Skip generic buffers.
- **expertise**: domain areas the paper signals the lab works in (e.g. "structural biology", "synthetic biology", "computational neuroscience"). At most three per paper.

## Hard rules

1. Output strict JSON matching the schema below. No prose, no markdown, no code fences.
2. Reject vague capabilities ("advanced techniques", "modern equipment"). Skip the entry rather than including a vague one.
3. Use the abstract as ground truth for `evidence`. Do not paraphrase beyond ~20 words; do not invent facts.
4. Use MeSH terms as a structured prior — items confirmed by MeSH headings are preferred.
5. If a category has no defensible entries, return an empty array for it. An empty result is fine.
6. Treat the paper year as a recency hint. Older papers represent capabilities the lab has used historically; this is still useful but the prompt does not require you to mark it.

## Schema

```json
{
  "techniques": [{"name": "<short canonical name>", "evidence": "<≤20-word quote/paraphrase>"}],
  "organisms": [{"name": "<short canonical name>", "evidence": "<…>"}],
  "equipment": [{"name": "<short canonical name>", "evidence": "<…>"}],
  "reagents": [{"name": "<short canonical name>", "evidence": "<…>"}],
  "expertise": [{"domain": "<short canonical name>", "evidence": "<…>"}]
}
```

Output ONLY the JSON object."""


@pytest.fixture(scope="module")
def capability_papers() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text())


async def _extract(paper: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    user_prompt = (
        f"Title: {paper['title']}\n"
        f"Year: {paper.get('year', 'unknown')}\n"
        f"MeSH terms: {', '.join(paper.get('mesh_terms') or []) or 'none'}\n\n"
        f"Abstract:\n{paper['abstract']}\n\n"
        "Output the JSON object now:"
    )

    response = await acompletion(
        model="claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": CAPABILITY_EXTRACTION_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=2000,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result  # type: ignore[return-value]
    except json.JSONDecodeError:
        pass
    return {"techniques": [], "organisms": [], "equipment": [], "reagents": [], "expertise": []}


def _canon(name: str) -> str:
    return " ".join(name.lower().strip().split())


def _keyword_overlap(expected: str, extracted: str) -> bool:
    """Match if any meaningful expected token appears in the extracted name."""
    stop = {"the", "a", "an", "of", "and", "for", "in"}
    expected_tokens = {
        t for t in expected.replace("-", " ").replace("/", " ").split()
        if t not in stop and len(t) > 2
    }
    extracted_tokens = set(extracted.replace("-", " ").replace("/", " ").split())
    if not expected_tokens:
        return expected.strip() in extracted.strip()
    return bool(expected_tokens & extracted_tokens)


@pytest.mark.extraction
@pytest.mark.asyncio
class TestCapabilityExtraction:
    """LLM-gated precision/recall over the labeled fixture set."""

    async def test_techniques_recall(
        self, capability_papers: list[dict[str, Any]]
    ) -> None:
        total_expected = 0
        total_found = 0
        for paper in capability_papers:
            result = await _extract(paper)
            extracted = {_canon(t.get("name", "")) for t in result.get("techniques", [])}
            for expected_name in paper["expected"]["techniques"]:
                total_expected += 1
                if any(_keyword_overlap(_canon(expected_name), e) for e in extracted):
                    total_found += 1
        recall = total_found / total_expected if total_expected else 0.0
        assert recall >= 0.70, (
            f"techniques recall {recall:.2f} (got {total_found}/{total_expected})"
        )

    async def test_organisms_recall(
        self, capability_papers: list[dict[str, Any]]
    ) -> None:
        total_expected = 0
        total_found = 0
        for paper in capability_papers:
            result = await _extract(paper)
            extracted = {_canon(o.get("name", "")) for o in result.get("organisms", [])}
            for expected_name in paper["expected"]["organisms"]:
                total_expected += 1
                if any(_keyword_overlap(_canon(expected_name), e) for e in extracted):
                    total_found += 1
        recall = total_found / total_expected if total_expected else 1.0
        assert recall >= 0.65, (
            f"organisms recall {recall:.2f} ({total_found}/{total_expected})"
        )

    async def test_techniques_precision(
        self, capability_papers: list[dict[str, Any]]
    ) -> None:
        """At most 30% of extracted techniques are entirely off-base."""
        off_base = 0
        total = 0
        for paper in capability_papers:
            result = await _extract(paper)
            expected = {_canon(n) for n in paper["expected"]["techniques"]}
            for t in result.get("techniques", []):
                total += 1
                cn = _canon(t.get("name", ""))
                if not any(_keyword_overlap(e, cn) for e in expected):
                    off_base += 1
        if total == 0:
            pytest.skip("no techniques extracted at all — separate failure")
        precision = 1 - (off_base / total)
        assert precision >= 0.70, (
            f"techniques precision {precision:.2f} ({off_base} off-base of {total})"
        )

    async def test_no_vague_techniques(
        self, capability_papers: list[dict[str, Any]]
    ) -> None:
        """The extractor should reject vague capability claims per the prompt."""
        forbidden_substrings = [
            "advanced", "modern", "novel", "cutting-edge", "state-of-the-art",
        ]
        offenders: list[str] = []
        for paper in capability_papers:
            result = await _extract(paper)
            for t in result.get("techniques", []):
                name = t.get("name", "")
                if any(sub in name.lower() for sub in forbidden_substrings):
                    offenders.append(name)
        assert not offenders, f"Vague techniques leaked through: {offenders}"
