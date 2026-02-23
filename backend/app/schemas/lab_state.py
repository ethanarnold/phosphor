"""Lab state schemas - the compressed representation (~2K tokens target)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Equipment(BaseModel):
    """Laboratory equipment with capabilities."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    limitations: str | None = Field(default=None, max_length=500)


class Technique(BaseModel):
    """Laboratory technique with proficiency level."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    proficiency: Literal["expert", "competent", "learning"]
    notes: str | None = Field(default=None, max_length=500)


class Expertise(BaseModel):
    """Domain expertise with confidence level."""

    model_config = ConfigDict(strict=True)

    domain: str = Field(..., min_length=1, max_length=200)
    confidence: Literal["high", "medium", "low"]


class Organism(BaseModel):
    """Model organism available in the lab."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    strains: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=500)


class Reagent(BaseModel):
    """Key reagent/material available."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class ExperimentSummary(BaseModel):
    """Compressed experimental outcome."""

    model_config = ConfigDict(strict=True)

    technique: str = Field(..., min_length=1, max_length=200)
    outcome: Literal["success", "partial", "failed"]
    insight: str = Field(..., min_length=1, max_length=500)


class ResourceConstraints(BaseModel):
    """Lab resource constraints."""

    model_config = ConfigDict(strict=True)

    budget_notes: str | None = Field(default=None, max_length=500)
    time_constraints: str | None = Field(default=None, max_length=500)
    personnel_notes: str | None = Field(default=None, max_length=500)


class LabStateData(BaseModel):
    """The compressed lab state representation.

    Target: ~2K tokens when serialized to JSON.
    """

    model_config = ConfigDict(strict=True)

    equipment: list[Equipment] = Field(default_factory=list, max_length=50)
    techniques: list[Technique] = Field(default_factory=list, max_length=50)
    expertise: list[Expertise] = Field(default_factory=list, max_length=30)
    organisms: list[Organism] = Field(default_factory=list, max_length=20)
    reagents: list[Reagent] = Field(default_factory=list, max_length=50)
    experimental_history: list[ExperimentSummary] = Field(
        default_factory=list, max_length=30
    )
    resource_constraints: ResourceConstraints = Field(
        default_factory=ResourceConstraints
    )

    # Metadata
    signal_count: int = Field(default=0, ge=0)


class LabStateResponse(BaseModel):
    """API response for lab state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    version: int
    state: LabStateData
    token_count: int | None
    created_at: datetime
    created_by: str | None


class LabStateHistoryResponse(BaseModel):
    """API response for lab state history."""

    model_config = ConfigDict(strict=True)

    states: list[LabStateResponse]
    total: int
