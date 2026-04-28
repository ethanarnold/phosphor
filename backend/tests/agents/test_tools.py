"""Tests for the tool registry and the pure-logic parts of each tool.

DB-backed tool implementations are exercised at integration level in Phase 2;
here we only pin down contract details: schema shape, lab_id is closed over,
unknown tools error out, category resolution works.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.tools import (
    _CATEGORY_ATTRS,
    ToolRegistry,
    ToolSpec,
    _list_capabilities_impl,
    build_default_registry,
)


def _fake_session() -> Any:
    return AsyncMock()


def _fake_settings() -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(llm_model="claude-sonnet-4-6", embedding_model="text-embedding-3-small")


def test_registry_schemas_shape() -> None:
    registry = build_default_registry(
        session=_fake_session(), settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    schemas = registry.schemas()
    assert {s["function"]["name"] for s in schemas} == {
        "get_lab_state",
        "search_experiments",
        "search_literature",
        "list_capabilities",
    }
    # OpenAI-tools envelope
    for s in schemas:
        assert s["type"] == "function"
        assert "parameters" in s["function"]
        # lab_id must NOT be a parameter — it's closed over per session.
        assert "lab_id" not in s["function"]["parameters"].get("properties", {})


def test_registry_has_and_names() -> None:
    registry = build_default_registry(
        session=_fake_session(), settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    assert registry.has("get_lab_state")
    assert not registry.has("not_a_tool")
    assert set(registry.names()) == {
        "get_lab_state",
        "search_experiments",
        "search_literature",
        "list_capabilities",
    }


@pytest.mark.asyncio
async def test_registry_dispatch_unknown_raises() -> None:
    registry = ToolRegistry([])
    with pytest.raises(KeyError):
        await registry.dispatch("nope", {})


@pytest.mark.asyncio
async def test_registry_dispatch_invokes_impl() -> None:
    received: list[dict[str, Any]] = []

    async def echo(args: dict[str, Any]) -> Any:
        received.append(args)
        return {"ok": True, "args": args}

    spec = ToolSpec(
        name="echo",
        schema={
            "name": "echo",
            "description": "x",
            "parameters": {"type": "object", "properties": {}},
        },
        impl=echo,
    )
    registry = ToolRegistry([spec])
    result = await registry.dispatch("echo", {"a": 1})
    assert result == {"ok": True, "args": {"a": 1}}
    assert received == [{"a": 1}]


@pytest.mark.asyncio
async def test_search_experiments_rejects_empty_query() -> None:
    registry = build_default_registry(
        session=_fake_session(), settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    result = await registry.dispatch("search_experiments", {"query": ""})
    assert result == {"error": "query is required"}


@pytest.mark.asyncio
async def test_search_literature_rejects_empty_query() -> None:
    registry = build_default_registry(
        session=_fake_session(), settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    result = await registry.dispatch("search_literature", {"query": ""})
    assert result == {"error": "query is required"}


@pytest.mark.asyncio
async def test_search_literature_filters_to_paper_kind() -> None:
    """The tool wraps hybrid_search but must drop signal/experiment hits."""
    from datetime import UTC, datetime

    from app.services.search import SearchHit

    fake_session = _fake_session()
    settings = _fake_settings()
    lab_id = uuid.uuid4()

    paper_id = uuid.uuid4()
    sig_id = uuid.uuid4()
    paper_hit = SearchHit(
        kind="paper",
        id=paper_id,
        score=0.91,
        snippet="A relevant abstract.",
        matched_by="embedding",
        title="Spatial transcriptomics in microglia",
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    signal_hit = SearchHit(
        kind="signal",
        id=sig_id,
        score=0.7,
        snippet="An experiment row.",
        matched_by="keyword",
        signal_type="experiment",
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )

    async def fake_hybrid(**_kwargs: Any) -> list[SearchHit]:
        return [paper_hit, signal_hit]

    with patch("app.agents.tools.hybrid_search", side_effect=fake_hybrid):
        registry = build_default_registry(session=fake_session, settings=settings, lab_id=lab_id)
        result = await registry.dispatch("search_literature", {"query": "microglia"})

    assert result["query"] == "microglia"
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["title"] == "Spatial transcriptomics in microglia"
    assert match["score"] == 0.91


@pytest.mark.asyncio
async def test_list_capabilities_rejects_empty_category() -> None:
    registry = build_default_registry(
        session=_fake_session(), settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    result = await registry.dispatch("list_capabilities", {"category": ""})
    assert result == {"error": "category is required"}


def test_category_synonyms_resolve_to_real_attrs() -> None:
    # Synonyms must point at real LabStateData fields.
    real = {
        "equipment",
        "techniques",
        "expertise",
        "organisms",
        "reagents",
        "experimental_history",
    }
    for cat, attr in _CATEGORY_ATTRS.items():
        assert attr in real, f"{cat} → {attr} not a valid state attribute"


@pytest.mark.asyncio
async def test_list_capabilities_unknown_category_returns_valid_list() -> None:
    session = AsyncMock()
    result = await _list_capabilities_impl(
        session=session, lab_id=uuid.uuid4(), category="nonsense"
    )
    assert result["error"] == "Unknown category"
    assert "valid_categories" in result


@pytest.mark.asyncio
async def test_list_capabilities_empty_state_returns_note() -> None:
    session = AsyncMock()
    exec_result = AsyncMock()
    exec_result.scalar_one_or_none = lambda: None
    session.execute.return_value = exec_result
    result = await _list_capabilities_impl(
        session=session, lab_id=uuid.uuid4(), category="equipment"
    )
    assert result["items"] == []
    assert "No lab state" in result["note"]


@pytest.mark.asyncio
async def test_list_capabilities_returns_items_from_state() -> None:
    session = AsyncMock()
    state_row = type(
        "Row",
        (),
        {
            "state": {
                "equipment": [
                    {
                        "name": "Illumina NovaSeq 6000",
                        "capabilities": ["Short-read sequencing"],
                        "limitations": None,
                    }
                ],
                "techniques": [],
                "expertise": [],
                "organisms": [],
                "reagents": [],
                "experimental_history": [],
                "resource_constraints": {
                    "budget_notes": None,
                    "time_constraints": None,
                    "personnel_notes": None,
                },
                "signal_count": 1,
            }
        },
    )()
    exec_result = AsyncMock()
    exec_result.scalar_one_or_none = lambda: state_row
    session.execute.return_value = exec_result

    result = await _list_capabilities_impl(
        session=session, lab_id=uuid.uuid4(), category="sequencing"
    )
    assert result["resolved_to"] == "techniques"  # sequencing → techniques
    assert result["count"] == 0

    result2 = await _list_capabilities_impl(
        session=session, lab_id=uuid.uuid4(), category="equipment"
    )
    assert result2["count"] == 1
    assert result2["items"][0]["name"] == "Illumina NovaSeq 6000"


@pytest.mark.asyncio
async def test_get_lab_state_handles_missing_state() -> None:
    session = AsyncMock()
    exec_result = AsyncMock()
    exec_result.scalar_one_or_none = lambda: None
    session.execute.return_value = exec_result

    registry = build_default_registry(
        session=session, settings=_fake_settings(), lab_id=uuid.uuid4()
    )
    result = await registry.dispatch("get_lab_state", {})
    assert result["version"] is None
    assert "No lab state" in result["note"]


@pytest.mark.asyncio
async def test_lab_id_is_closed_over_and_not_overridable_by_args() -> None:
    """Security contract: a malicious `lab_id` in tool args must not change scope."""
    bound_lab = uuid.uuid4()
    attacker_lab = uuid.uuid4()

    with patch(
        "app.agents.tools._get_lab_state_impl",
        new=AsyncMock(return_value={"ok": True, "lab_id_used": "redacted"}),
    ) as impl:
        registry = build_default_registry(
            session=_fake_session(), settings=_fake_settings(), lab_id=bound_lab
        )
        # Even if the model invents a lab_id argument, the impl only ever
        # receives `bound_lab` via the closure — the arg is discarded.
        await registry.dispatch("get_lab_state", {"lab_id": str(attacker_lab)})
        assert impl.await_args.kwargs["lab_id"] == bound_lab
