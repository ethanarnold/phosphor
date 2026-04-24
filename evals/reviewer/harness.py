"""Reviewer eval harness — runs the real agent loop against fixture data.

Each case carries a complete lab state inline, so the harness doesn't need
a database; the ToolRegistry is built from an in-memory stub that serves
the fixture's `lab_state`. That means the *real* LiteLLM completion is
invoked, which is the point — we're scoring what the actual model does.

Callers should skip the test module when `ANTHROPIC_API_KEY` is absent.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Make backend importable when running evals out of tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.agents.loop import AgentResult, run_agent  # noqa: E402
from app.agents.prompts import load_prompt  # noqa: E402
from app.agents.tools import ToolRegistry, ToolSpec  # noqa: E402
from app.schemas.lab_state import LabStateData  # noqa: E402


@dataclass
class EvalScore:
    """Three-axis grade for a single case."""

    case_id: str
    grounding: bool
    coverage: bool
    actionability: bool
    final_answer: str
    tool_calls: list[tuple[str, dict[str, Any]]]
    notes: str = ""

    @property
    def all_pass(self) -> bool:
        return self.grounding and self.coverage and self.actionability


# ---------- Tool-registry stub for fixtures ----------


def _matches_snippet(query: str, blob: str) -> bool:
    return query.lower() in blob.lower()


def _flatten_state_for_search(state: dict[str, Any]) -> list[tuple[str, str]]:
    """Produce (kind, text) pairs so `search_experiments` can do a keyword match."""
    pairs: list[tuple[str, str]] = []
    for eh in state.get("experimental_history", []):
        pairs.append(
            (
                f"exp:{eh.get('technique', '?')}",
                f"{eh.get('technique', '')} {eh.get('outcome', '')} {eh.get('insight', '')}",
            )
        )
    for t in state.get("techniques", []):
        notes = t.get("notes") or ""
        pairs.append((f"tech:{t['name']}", f"{t['name']} {t.get('proficiency', '')} {notes}"))
    for o in state.get("organisms", []):
        pairs.append((f"org:{o['name']}", f"{o['name']} {' '.join(o.get('strains', []))}"))
    for e in state.get("equipment", []):
        pairs.append(
            (
                f"equip:{e['name']}",
                f"{e['name']} {' '.join(e.get('capabilities', []))} {e.get('limitations') or ''}",
            )
        )
    return pairs


def _build_fixture_registry(state: dict[str, Any]) -> ToolRegistry:
    """A ToolRegistry backed by in-memory fixture data (no DB)."""

    async def get_lab_state(_args: dict[str, Any]) -> Any:
        return {"version": 1, "state": state}

    async def search_experiments(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}
        pairs = _flatten_state_for_search(state)
        matches = [
            {"id": kind, "snippet": text[:240], "matched_by": "keyword"}
            for kind, text in pairs
            if _matches_snippet(query, text)
        ]
        total_exp = len(state.get("experimental_history", []))
        return {
            "query": query,
            "total_experiments_in_lab": total_exp,
            "matches": matches[:10],
        }

    async def list_capabilities(args: dict[str, Any]) -> Any:
        category = str(args.get("category", "")).strip().lower()
        mapping = {
            "equipment": "equipment",
            "techniques": "techniques",
            "expertise": "expertise",
            "organisms": "organisms",
            "reagents": "reagents",
            "experimental_history": "experimental_history",
            "sequencing": "techniques",
            "imaging": "equipment",
            "microscopy": "equipment",
        }
        if category not in mapping:
            return {"error": "Unknown category", "category": category}
        attr = mapping[category]
        items = state.get(attr, [])
        return {"category": category, "resolved_to": attr, "items": items, "count": len(items)}

    # Validate fixture lab state against the real schema as a safety net.
    LabStateData.model_validate(state)

    return ToolRegistry(
        [
            ToolSpec(
                "get_lab_state",
                {
                    "name": "get_lab_state",
                    "description": "Fetch the lab's current compressed state.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
                get_lab_state,
            ),
            ToolSpec(
                "search_experiments",
                {
                    "name": "search_experiments",
                    "description": "Search experiments, techniques, organisms, equipment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
                search_experiments,
            ),
            ToolSpec(
                "list_capabilities",
                {
                    "name": "list_capabilities",
                    "description": "List entries in a specific capability category.",
                    "parameters": {
                        "type": "object",
                        "properties": {"category": {"type": "string"}},
                        "required": ["category"],
                    },
                },
                list_capabilities,
            ),
        ]
    )


# ---------- Scoring ----------

_NEXT_STEP_DEFAULT_RE = re.compile(
    r"\b(collaborat|partner with|drop|de-?scope|months? of (?:method|protocol)|hire|training|"
    r"scope down|cut the)\b",
    re.IGNORECASE,
)


def _flatten_all_tool_text(case: dict[str, Any]) -> str:
    """Text blob of everything the agent could plausibly *ground* against —
    used to distinguish a hallucinated name from a real one."""
    chunks: list[str] = []
    state = case["lab_state"]
    for section in ("equipment", "techniques", "expertise", "organisms", "reagents"):
        for item in state.get(section, []):
            chunks.append(" ".join(str(v) for v in item.values() if v))
    for eh in state.get("experimental_history", []):
        chunks.append(f"{eh.get('technique', '')} {eh.get('insight', '')}")
    return " ".join(chunks).lower()


def _score_grounding(result: AgentResult) -> bool:
    """Every run must include a get_lab_state call and ≥1 evidence call.

    This is coarse — a full grounding check would inspect each factual claim
    in the final answer against tool result bodies. For v1, requiring
    get_lab_state + another tool call proves the agent used tools at all;
    pure-hallucination runs (no tool calls) fail this axis outright.
    """
    names = [c.tool_name for c in result.tool_calls]
    if not names:
        return False
    if "get_lab_state" not in names:
        return False
    return len(names) >= 2


def _score_coverage(result: AgentResult, case: dict[str, Any]) -> bool:
    """Answer must mention ≥ (n-1) of the expected_missing gaps for strong cases,
    or ≥1 of expected_grounded for well-matched cases."""
    answer = (result.final_answer or "").lower()
    expected_missing = [m.lower() for m in case.get("expected_missing", [])]
    expected_grounded = [g.lower() for g in case.get("expected_grounded", [])]

    if expected_missing:
        hits = sum(1 for m in expected_missing if m in answer)
        # Accept if the answer flags at least half of the intended gaps
        # (rounded up). This tolerates synonym choice but still demands
        # the agent recognized the main weaknesses.
        threshold = max(1, (len(expected_missing) + 1) // 2)
        return hits >= threshold

    # Strong-fit cases: answer should explicitly acknowledge a grounded capability.
    return any(g in answer for g in expected_grounded)


def _score_actionability(result: AgentResult, case: dict[str, Any]) -> bool:
    """Final answer must recommend one concrete next step."""
    answer = result.final_answer or ""
    if not answer.strip():
        return False
    keywords = case.get("expected_next_step_keywords", [])
    if keywords:
        pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
        if pattern.search(answer):
            return True
    return bool(_NEXT_STEP_DEFAULT_RE.search(answer))


async def run_case(case: dict[str, Any], *, model: str) -> EvalScore:
    """Run the agent against a single case and score it."""
    registry = _build_fixture_registry(case["lab_state"])
    system_prompt = load_prompt("reviewer")
    result = await run_agent(
        system_prompt=system_prompt,
        user_message=case["aim"],
        registry=registry,
        model=model,
        max_turns=8,
    )
    return EvalScore(
        case_id=case["id"],
        grounding=_score_grounding(result),
        coverage=_score_coverage(result, case),
        actionability=_score_actionability(result, case),
        final_answer=result.final_answer or "",
        tool_calls=[(c.tool_name, c.arguments) for c in result.tool_calls],
        notes=f"stop={result.stop_reason} turns={result.turn_count}",
    )
