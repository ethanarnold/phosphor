"""Agent tool-calling loop over LiteLLM.

Each turn: send messages + tool schemas → provider. If the assistant emits
tool_calls, dispatch them against the registry, append results as role=tool
messages, and continue. Terminate when the model replies without tool_calls
or when MAX_TURNS is reached.

v1 is non-streaming and single-shot. A session that has not concluded in
MAX_TURNS turns has failed — surface to the caller rather than running on.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from litellm import acompletion

from app.agents.tools import ToolRegistry

MAX_TURNS: int = 8

Completion = Callable[..., Awaitable[Any]]


@dataclass
class ToolCallRecord:
    """One tool_call round-trip: request args + the dispatched result."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    error: str | None = None


@dataclass
class AgentResult:
    """Outcome of a single agent run."""

    final_answer: str | None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    stop_reason: str = "complete"  # "complete" | "max_turns" | "error"
    error: str | None = None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Tool-call arguments arrive as a JSON string in OpenAI-shape responses.

    LiteLLM normalizes providers toward this shape, but some returns are
    already decoded dicts — accept both. Invalid JSON yields an empty dict;
    the loop reports the parse error back to the model so it can retry.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        parsed = json.loads(s)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    return {}


def _tool_calls_from_message(msg: Any) -> list[Any]:
    """Extract `tool_calls` from a response message (object or dict)."""
    calls = getattr(msg, "tool_calls", None)
    if calls is None and isinstance(msg, dict):
        calls = msg.get("tool_calls")
    return calls or []


def _content_from_message(msg: Any) -> str | None:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if isinstance(content, list):
        # Some providers return content parts; concat the text ones.
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        return "".join(parts) or None
    return content


async def run_agent(
    *,
    system_prompt: str,
    user_message: str,
    registry: ToolRegistry,
    model: str,
    max_turns: int = MAX_TURNS,
    temperature: float = 0.2,
    completion: Completion | None = None,
) -> AgentResult:
    """Run the tool-calling loop against `registry`, returning when complete.

    `completion` defaults to `litellm.acompletion`; tests inject a stub.
    """
    call = completion or acompletion

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tool_calls_made: list[ToolCallRecord] = []

    for turn in range(1, max_turns + 1):
        try:
            response = await call(
                model=model,
                messages=messages,
                tools=registry.schemas(),
                temperature=temperature,
            )
        except Exception as e:
            return AgentResult(
                final_answer=None,
                tool_calls=tool_calls_made,
                messages=messages,
                turn_count=turn - 1,
                stop_reason="error",
                error=f"Provider error: {e}",
            )

        try:
            message = response.choices[0].message
        except (AttributeError, IndexError) as e:
            return AgentResult(
                final_answer=None,
                tool_calls=tool_calls_made,
                messages=messages,
                turn_count=turn,
                stop_reason="error",
                error=f"Malformed response: {e}",
            )

        calls = _tool_calls_from_message(message)

        if not calls:
            final = _content_from_message(message)
            messages.append({"role": "assistant", "content": final or ""})
            return AgentResult(
                final_answer=final,
                tool_calls=tool_calls_made,
                messages=messages,
                turn_count=turn,
                stop_reason="complete",
            )

        # Persist the assistant turn (including the tool_calls payload) so the
        # follow-up `role=tool` messages have the `tool_call_id` to reference.
        assistant_entry: dict[str, Any] = {
            "role": "assistant",
            "content": _content_from_message(message) or "",
            "tool_calls": [
                {
                    "id": getattr(c, "id", None) or (isinstance(c, dict) and c.get("id")) or "",
                    "type": "function",
                    "function": {
                        "name": _call_name(c),
                        "arguments": _call_raw_arguments(c),
                    },
                }
                for c in calls
            ],
        }
        messages.append(assistant_entry)

        for call_obj in calls:
            name = _call_name(call_obj)
            call_id = (
                getattr(call_obj, "id", None)
                or (isinstance(call_obj, dict) and call_obj.get("id"))
                or ""
            )
            raw_args = _call_raw_arguments(call_obj)

            error: str | None = None
            result: Any
            try:
                args = _parse_arguments(raw_args)
            except json.JSONDecodeError as e:
                args = {}
                error = f"Could not parse arguments JSON: {e}"
                result = {"error": error}
            else:
                if not registry.has(name):
                    error = f"Unknown tool: {name}"
                    result = {"error": error}
                else:
                    try:
                        result = await registry.dispatch(name, args)
                    except Exception as e:  # surface tool errors to the model
                        error = f"Tool execution failed: {e}"
                        result = {"error": error}

            tool_calls_made.append(
                ToolCallRecord(
                    tool_name=name, arguments=args, result=result, error=error
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": _to_tool_content(result),
                }
            )

    return AgentResult(
        final_answer=None,
        tool_calls=tool_calls_made,
        messages=messages,
        turn_count=max_turns,
        stop_reason="max_turns",
        error=f"Agent did not conclude within {max_turns} turns",
    )


def _call_name(call_obj: Any) -> str:
    fn = getattr(call_obj, "function", None)
    if fn is not None:
        name = getattr(fn, "name", None)
        if name:
            return str(name)
    if isinstance(call_obj, dict):
        return str(call_obj.get("function", {}).get("name", ""))
    return ""


def _call_raw_arguments(call_obj: Any) -> Any:
    fn = getattr(call_obj, "function", None)
    if fn is not None:
        args = getattr(fn, "arguments", None)
        if args is not None:
            return args
    if isinstance(call_obj, dict):
        return call_obj.get("function", {}).get("arguments", "")
    return ""


def _to_tool_content(result: Any) -> str:
    """Serialize a tool result for the `content` field of a role=tool message."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)
