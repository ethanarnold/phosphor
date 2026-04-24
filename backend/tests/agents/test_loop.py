"""Unit tests for the agent tool-calling loop.

The LiteLLM completion call is stubbed so the loop can be exercised without
network access. The stub yields a canned sequence of responses, matching the
shape LiteLLM returns after translating Anthropic tool-use events.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.loop import MAX_TURNS, AgentResult, run_agent
from app.agents.tools import ToolRegistry, ToolSpec

# --------- Helpers to fabricate provider responses ---------


def _fn_call(name: str, args: dict[str, Any], call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _assistant_response(
    *,
    content: str | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls or None)
            )
        ]
    )


def _scripted_completion(responses: list[SimpleNamespace]):  # noqa: ANN202
    """Return an async stub that pops one canned response per call."""
    queue = list(responses)
    calls_seen: list[dict[str, Any]] = []

    async def _call(**kwargs: Any) -> SimpleNamespace:
        calls_seen.append(kwargs)
        if not queue:
            raise AssertionError("Completion called more times than scripted")
        return queue.pop(0)

    _call.calls_seen = calls_seen  # type: ignore[attr-defined]
    return _call


# --------- A trivial in-memory registry ---------


def _registry_with(probe_calls: list[tuple[str, dict[str, Any]]]) -> ToolRegistry:
    async def get_lab_state(args: dict[str, Any]) -> Any:
        probe_calls.append(("get_lab_state", args))
        return {"techniques": [{"name": "Western blot", "proficiency": "expert"}]}

    async def search_experiments(args: dict[str, Any]) -> Any:
        probe_calls.append(("search_experiments", args))
        return {"query": args.get("query"), "matches": []}

    async def explode(_args: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    return ToolRegistry(
        [
            ToolSpec(
                "get_lab_state",
                {
                    "name": "get_lab_state",
                    "description": "fetch state",
                    "parameters": {"type": "object", "properties": {}},
                },
                get_lab_state,
            ),
            ToolSpec(
                "search_experiments",
                {
                    "name": "search_experiments",
                    "description": "search",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
                search_experiments,
            ),
            ToolSpec(
                "explode",
                {
                    "name": "explode",
                    "description": "raise",
                    "parameters": {"type": "object", "properties": {}},
                },
                explode,
            ),
        ]
    )


# --------- Tests ---------


@pytest.mark.asyncio
async def test_loop_dispatches_two_tool_calls_then_terminates() -> None:
    probe: list[tuple[str, dict[str, Any]]] = []
    registry = _registry_with(probe)

    completion = _scripted_completion(
        [
            _assistant_response(
                content=None,
                tool_calls=[_fn_call("get_lab_state", {}, "call_1")],
            ),
            _assistant_response(
                content=None,
                tool_calls=[
                    _fn_call("search_experiments", {"query": "CRISPR"}, "call_2")
                ],
            ),
            _assistant_response(content="Final critique: grounded answer."),
        ]
    )

    result = await run_agent(
        system_prompt="reviewer",
        user_message="please critique",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )

    assert isinstance(result, AgentResult)
    assert result.stop_reason == "complete"
    assert result.turn_count == 3
    assert result.final_answer == "Final critique: grounded answer."
    assert [c.tool_name for c in result.tool_calls] == [
        "get_lab_state",
        "search_experiments",
    ]
    assert result.tool_calls[1].arguments == {"query": "CRISPR"}
    assert probe == [
        ("get_lab_state", {}),
        ("search_experiments", {"query": "CRISPR"}),
    ]


@pytest.mark.asyncio
async def test_loop_injects_tool_results_into_message_history() -> None:
    probe: list[tuple[str, dict[str, Any]]] = []
    registry = _registry_with(probe)

    completion = _scripted_completion(
        [
            _assistant_response(
                tool_calls=[_fn_call("get_lab_state", {}, "call_A")]
            ),
            _assistant_response(content="done"),
        ]
    )

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )

    roles = [m["role"] for m in result.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    tool_msg = result.messages[3]
    assert tool_msg["name"] == "get_lab_state"
    assert tool_msg["tool_call_id"] == "call_A"
    body = json.loads(tool_msg["content"])
    assert body["techniques"][0]["name"] == "Western blot"


@pytest.mark.asyncio
async def test_loop_surfaces_tool_errors_to_the_model_not_the_caller() -> None:
    probe: list[tuple[str, dict[str, Any]]] = []
    registry = _registry_with(probe)

    completion = _scripted_completion(
        [
            _assistant_response(
                tool_calls=[_fn_call("explode", {}, "call_X")]
            ),
            _assistant_response(content="recovered"),
        ]
    )

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )

    assert result.stop_reason == "complete"
    assert result.final_answer == "recovered"
    assert result.tool_calls[0].error is not None
    assert "boom" in result.tool_calls[0].error
    tool_message_body = json.loads(result.messages[3]["content"])
    assert "error" in tool_message_body


@pytest.mark.asyncio
async def test_loop_handles_unknown_tool_by_reporting_back() -> None:
    registry = _registry_with([])
    completion = _scripted_completion(
        [
            _assistant_response(
                tool_calls=[_fn_call("nope", {}, "call_Z")]
            ),
            _assistant_response(content="ok"),
        ]
    )

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )
    assert result.stop_reason == "complete"
    assert result.tool_calls[0].error == "Unknown tool: nope"


@pytest.mark.asyncio
async def test_loop_terminates_at_max_turns_when_model_wont_stop() -> None:
    registry = _registry_with([])

    # Every response keeps issuing a tool call — loop must cap.
    responses = [
        _assistant_response(
            tool_calls=[_fn_call("get_lab_state", {}, f"call_{i}")]
        )
        for i in range(MAX_TURNS + 2)
    ]
    completion = _scripted_completion(responses)

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
        max_turns=3,
    )
    assert result.stop_reason == "max_turns"
    assert result.final_answer is None
    assert result.turn_count == 3
    assert len(result.tool_calls) == 3


@pytest.mark.asyncio
async def test_loop_recovers_from_malformed_arguments_json() -> None:
    registry = _registry_with([])
    # Construct a call with a broken arguments string.
    broken_call = SimpleNamespace(
        id="call_bad",
        type="function",
        function=SimpleNamespace(name="search_experiments", arguments="{not json"),
    )
    completion = _scripted_completion(
        [
            _assistant_response(tool_calls=[broken_call]),
            _assistant_response(content="fine"),
        ]
    )

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=completion,
    )
    assert result.stop_reason == "complete"
    assert result.tool_calls[0].error is not None
    assert "parse" in result.tool_calls[0].error.lower()


@pytest.mark.asyncio
async def test_loop_surfaces_provider_errors() -> None:
    registry = _registry_with([])

    async def _boom(**_: Any) -> Any:
        raise RuntimeError("network down")

    result = await run_agent(
        system_prompt="sys",
        user_message="hi",
        registry=registry,
        model="claude-sonnet-4-6",
        completion=_boom,
    )
    assert result.stop_reason == "error"
    assert result.error is not None
    assert "network down" in result.error
