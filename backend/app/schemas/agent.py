"""Pydantic schemas for the reviewer agent API."""

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
