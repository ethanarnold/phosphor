"""Experiment entry schemas — low-friction input surfaces."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperimentEntry(BaseModel):
    """Structured experiment entry."""

    model_config = ConfigDict(strict=True)

    date: datetime | None = None
    technique: str = Field(..., min_length=1, max_length=200)
    outcome: Literal["success", "partial", "failed"]
    notes: str = Field(..., min_length=1, max_length=5000)
    equipment_used: list[str] = Field(default_factory=list, max_length=20)
    organisms_used: list[str] = Field(default_factory=list, max_length=10)
    reagents_used: list[str] = Field(default_factory=list, max_length=30)


class QuickLogRequest(BaseModel):
    """Single free-text field for LLM-parsed experiment logging."""

    model_config = ConfigDict(strict=True)

    text: str = Field(..., min_length=1, max_length=4000)
    outcome_hint: Literal["success", "partial", "failed"] | None = None


class BulkExperimentRequest(BaseModel):
    """Bulk import from parsed rows (CSV)."""

    model_config = ConfigDict(strict=True)

    entries: list[ExperimentEntry] = Field(..., min_length=1, max_length=500)


class ExperimentCreateResponse(BaseModel):
    """Response for experiment creation — returns associated signal id."""

    model_config = ConfigDict(from_attributes=True)

    signal_id: uuid.UUID
    experiment: ExperimentEntry
    elapsed_ms: int | None = None


class BulkExperimentResponse(BaseModel):
    """Response for bulk import."""

    model_config = ConfigDict(strict=True)

    created: list[ExperimentCreateResponse]
    failed: list[dict[str, str]] = Field(default_factory=list)
