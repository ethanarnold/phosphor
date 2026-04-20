"""Protocol schemas for API validation."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProtocolPhase(BaseModel):
    """One phase of an experimental protocol."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    steps: list[str] = Field(..., min_length=1)
    duration_estimate: str | None = Field(default=None, max_length=100)
    materials_used: list[str] = Field(default_factory=list)


class ProtocolContent(BaseModel):
    """The structured content of a generated protocol."""

    model_config = ConfigDict(strict=True)

    phases: list[ProtocolPhase] = Field(..., min_length=2)
    materials: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(..., min_length=1)
    flagged_gaps: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class ProtocolResponse(BaseModel):
    """API response for a generated protocol."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    opportunity_id: uuid.UUID
    title: str
    content: ProtocolContent
    lab_state_version: int
    llm_model: str
    prompt_version: str
    status: Literal["generated", "reviewed", "archived"]
    created_at: datetime
    created_by: str


class ProtocolListResponse(BaseModel):
    """API response for listing protocols."""

    model_config = ConfigDict(strict=True)

    protocols: list[ProtocolResponse]
    total: int
