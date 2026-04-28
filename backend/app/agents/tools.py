"""Tool registry for the agent runtime.

Each tool is a pair of (JSON schema, async callable). The schema is the
OpenAI-compatible `tools=[...]` entry that LiteLLM translates for the provider.
The callable is invoked by the loop after the model emits a tool_call; its
return value (must be JSON-serializable) is what the model sees next.

Security invariant: tools do NOT accept `lab_id` in their schema. The registry
binds the current session's lab_id into the callable via `with_lab_id`, so a
prompt-injection attempt cannot redirect a tool against another lab's data.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.lab_state import LabState
from app.models.signal import RawSignal
from app.schemas.lab_state import LabStateData
from app.services.search import hybrid_search

ToolCallable = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    """A single tool: its OpenAI-compatible schema and the async implementation."""

    name: str
    schema: dict[str, Any]
    impl: ToolCallable


class ToolRegistry:
    """Mapping of tool-name → ToolSpec, invoked by the loop."""

    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {s.name: s for s in specs}

    def names(self) -> list[str]:
        return list(self._specs.keys())

    def schemas(self) -> list[dict[str, Any]]:
        """Return the `tools=[...]` list as LiteLLM expects it."""
        return [{"type": "function", "function": s.schema} for s in self._specs.values()]

    def has(self, name: str) -> bool:
        return name in self._specs

    async def dispatch(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self._specs:
            raise KeyError(f"Unknown tool: {name}")
        return await self._specs[name].impl(args)


# ---------- Tool implementations ----------


async def _get_lab_state_impl(*, session: AsyncSession, lab_id: uuid.UUID) -> dict[str, Any]:
    """Return the latest compressed lab state, or an explicit empty-state marker."""
    result = await session.execute(
        select(LabState).where(LabState.lab_id == lab_id).order_by(LabState.version.desc()).limit(1)
    )
    state = result.scalar_one_or_none()
    if state is None:
        return {"version": None, "state": None, "note": "No lab state on record."}
    return {
        "version": state.version,
        "token_count": state.token_count,
        "state": state.state,
    }


async def _search_experiments_impl(
    *,
    session: AsyncSession,
    settings: Settings,
    lab_id: uuid.UUID,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the lab's experiment signals (and related papers) for a query.

    Built on `hybrid_search` — keyword ILIKE over signal content plus embedding
    similarity over linked papers. Returns a compact list the model can cite.
    """
    limit = max(1, min(limit, 25))
    hits = await hybrid_search(
        session=session,
        settings=settings,
        lab_id=lab_id,
        query=query,
        limit=limit,
    )
    experiment_hits: list[dict[str, Any]] = []
    for h in hits:
        if h.kind != "signal":
            continue
        experiment_hits.append(
            {
                "id": str(h.id),
                "signal_type": h.signal_type,
                "snippet": h.snippet,
                "score": round(h.score, 3),
                "matched_by": h.matched_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
        )

    count_q = select(RawSignal).where(
        RawSignal.lab_id == lab_id, RawSignal.signal_type == "experiment"
    )
    total = len((await session.execute(count_q)).scalars().all())

    return {
        "query": query,
        "total_experiments_in_lab": total,
        "matches": experiment_hits,
    }


async def _search_literature_impl(
    *,
    session: AsyncSession,
    settings: Settings,
    lab_id: uuid.UUID,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the lab's ingested literature corpus (papers, abstracts) for a query.

    Mirrors `search_experiments` but filters to `kind="paper"` hits — keyword
    ILIKE on titles/abstracts plus embedding similarity. Returns the top
    matches so the model can cite specific papers when proposing a direction
    or strengthening an in-progress project.
    """
    limit = max(1, min(limit, 25))
    hits = await hybrid_search(
        session=session,
        settings=settings,
        lab_id=lab_id,
        query=query,
        limit=limit,
    )
    paper_hits: list[dict[str, Any]] = []
    for h in hits:
        if h.kind != "paper":
            continue
        paper_hits.append(
            {
                "id": str(h.id),
                "title": h.title,
                "snippet": h.snippet,
                "score": round(h.score, 3),
                "matched_by": h.matched_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
        )

    return {
        "query": query,
        "matches": paper_hits,
    }


_CATEGORY_ATTRS: dict[str, str] = {
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


async def _list_capabilities_impl(
    *, session: AsyncSession, lab_id: uuid.UUID, category: str
) -> dict[str, Any]:
    """List entries from the latest lab state for a specific capability category.

    Accepts the raw state-schema keys (`equipment`, `techniques`, …) plus a few
    natural-language synonyms (`sequencing`, `imaging`, `microscopy`) that map
    to the closest underlying list. Returns the full sub-list.
    """
    cat = category.strip().lower()
    if cat not in _CATEGORY_ATTRS:
        return {
            "category": category,
            "error": "Unknown category",
            "valid_categories": sorted(set(_CATEGORY_ATTRS.keys())),
        }

    result = await session.execute(
        select(LabState).where(LabState.lab_id == lab_id).order_by(LabState.version.desc()).limit(1)
    )
    state = result.scalar_one_or_none()
    if state is None:
        return {"category": category, "items": [], "note": "No lab state on record."}

    data = LabStateData.model_validate(state.state)
    attr = _CATEGORY_ATTRS[cat]
    items = getattr(data, attr)
    return {
        "category": category,
        "resolved_to": attr,
        "items": [i.model_dump() for i in items],
        "count": len(items),
    }


# ---------- Schemas ----------

_GET_LAB_STATE_SCHEMA: dict[str, Any] = {
    "name": "get_lab_state",
    "description": (
        "Fetch the lab's current compressed state — equipment, techniques, "
        "expertise, organisms, reagents, and a summary of past experiments. "
        "Call this FIRST to ground every critique in the lab's actual profile."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

_SEARCH_EXPERIMENTS_SCHEMA: dict[str, Any] = {
    "name": "search_experiments",
    "description": (
        "Search the lab's experiment log for a specific technique, target, "
        "organism, or keyword. Returns matching experiments with snippets and "
        "dates. Use this to check whether the lab has actually done a thing "
        "the user's aim assumes they can do."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword or short phrase, e.g. 'CRISPR', 'primary microglia', 'TREM2'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10, max 25).",
                "minimum": 1,
                "maximum": 25,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

_SEARCH_LITERATURE_SCHEMA: dict[str, Any] = {
    "name": "search_literature",
    "description": (
        "Search the lab's ingested literature corpus (PubMed / Semantic "
        "Scholar abstracts the lab has bookmarked or imported) for a topic, "
        "method, or target. Use this to surface what's emerging in the "
        "field and cite specific papers when proposing a direction."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic or short phrase, e.g. 'spatial transcriptomics microglia', 'TREM2 cleavage'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10, max 25).",
                "minimum": 1,
                "maximum": 25,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

_LIST_CAPABILITIES_SCHEMA: dict[str, Any] = {
    "name": "list_capabilities",
    "description": (
        "List the lab's entries in a specific capability category. Useful for "
        "confirming presence/absence of methods (e.g. sequencing, imaging) "
        "without a free-text search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": (
                    "One of: equipment, techniques, expertise, organisms, "
                    "reagents, experimental_history. Also accepts 'sequencing', "
                    "'imaging', 'microscopy' as convenience synonyms."
                ),
            }
        },
        "required": ["category"],
        "additionalProperties": False,
    },
}


def build_default_registry(
    *,
    session: AsyncSession,
    settings: Settings,
    lab_id: uuid.UUID,
) -> ToolRegistry:
    """Construct the registry for the reviewer agent, scoped to a single lab.

    `lab_id` is closed over in each impl — the model can never override it.
    """

    async def get_lab_state(_args: dict[str, Any]) -> Any:
        return await _get_lab_state_impl(session=session, lab_id=lab_id)

    async def search_experiments(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}
        limit = int(args.get("limit", 10))
        return await _search_experiments_impl(
            session=session,
            settings=settings,
            lab_id=lab_id,
            query=query,
            limit=limit,
        )

    async def search_literature(args: dict[str, Any]) -> Any:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}
        limit = int(args.get("limit", 10))
        return await _search_literature_impl(
            session=session,
            settings=settings,
            lab_id=lab_id,
            query=query,
            limit=limit,
        )

    async def list_capabilities(args: dict[str, Any]) -> Any:
        category = str(args.get("category", "")).strip()
        if not category:
            return {"error": "category is required"}
        return await _list_capabilities_impl(session=session, lab_id=lab_id, category=category)

    return ToolRegistry(
        [
            ToolSpec("get_lab_state", _GET_LAB_STATE_SCHEMA, get_lab_state),
            ToolSpec("search_experiments", _SEARCH_EXPERIMENTS_SCHEMA, search_experiments),
            ToolSpec("search_literature", _SEARCH_LITERATURE_SCHEMA, search_literature),
            ToolSpec("list_capabilities", _LIST_CAPABILITIES_SCHEMA, list_capabilities),
        ]
    )
