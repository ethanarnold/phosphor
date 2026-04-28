"""Pydantic schemas for the agent API (reviewer, directions, strengthen)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewerCreateRequest(BaseModel):
    """POST body — the draft aim / abstract the user wants critiqued."""

    model_config = ConfigDict(strict=True)

    input_text: str = Field(
        ...,
        min_length=20,
        max_length=4000,
        description="Draft aim, abstract, or paragraph to critique.",
    )


class DirectionsCreateRequest(BaseModel):
    """POST body — optional focus area to scope the directions search.

    Empty input is allowed — the agent will draw the focus from the lab
    state's strongest themes when no constraint is given.
    """

    model_config = ConfigDict(strict=True)

    input_text: str = Field(
        default="",
        max_length=2000,
        description=(
            "Optional focus area, theme, or constraint (e.g. "
            "'neurodegeneration', 'within-budget translational targets'). "
            "Leave empty to let the agent infer from the lab state."
        ),
    )


class StrengthenCreateRequest(BaseModel):
    """POST body — a description of the in-progress project to strengthen."""

    model_config = ConfigDict(strict=True)

    input_text: str = Field(
        ...,
        min_length=40,
        max_length=4000,
        description=(
            "Project description: the goal, the current state, what's "
            "stuck. The more concrete, the more grounded the next steps."
        ),
    )


class ReviewerCreateResponse(BaseModel):
    """Initial handshake response — the client polls using `session_id`."""

    model_config = ConfigDict(strict=True)

    session_id: uuid.UUID
    status: Literal["queued", "running", "complete", "error"]


class AgentMessageView(BaseModel):
    """One row of the agent transcript, shaped for the UI's tool trace."""

    model_config = ConfigDict(from_attributes=True, strict=True)

    id: uuid.UUID
    seq: int
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_name: str | None = None
    tool_args_json: dict[str, Any] | None = None
    tool_result_json: dict[str, Any] | None = None
    created_at: datetime


class ReviewerDetailResponse(BaseModel):
    """GET response — the full session state plus message log."""

    model_config = ConfigDict(from_attributes=True, strict=True)

    session_id: uuid.UUID
    status: Literal["queued", "running", "complete", "error"]
    input_text: str
    final_answer: str | None = None
    error: str | None = None
    turn_count: int
    model: str | None = None
    messages: list[AgentMessageView] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


# The directions and strengthen responses are structurally identical to the
# reviewer's — same status enum, same trace shape. Aliases keep route signatures
# self-documenting without duplicating the schema.
AgentCreateResponse = ReviewerCreateResponse
AgentDetailResponse = ReviewerDetailResponse
