"""Pydantic schemas for the ORCID lab state import API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.lab_state import (
    Equipment,
    Expertise,
    Organism,
    Reagent,
    Technique,
)

ImportStatus = Literal[
    "queued",
    "fetching",
    "extracting",
    "review",
    "committed",
    "failed",
    "cancelled",
]

# ORCID iDs are 16 digits in 4-4-4-4 groups; the final character is a Mod-11
# checksum digit that may be 0–9 or 'X' (representing 10).
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class LabStateImportCreate(BaseModel):
    """POST body — start an import for the supplied ORCID iD."""

    model_config = ConfigDict(strict=True)

    orcid_id: str = Field(..., min_length=19, max_length=19)

    @field_validator("orcid_id")
    @classmethod
    def _validate_orcid(cls, v: str) -> str:
        if not _ORCID_RE.match(v):
            raise ValueError("ORCID iD must match the format NNNN-NNNN-NNNN-NNNN")
        return v


class ImportProgress(BaseModel):
    """Progress milestones written by the Celery task as it runs."""

    model_config = ConfigDict(strict=True)

    papers_total: int | None = None
    papers_processed: int | None = None
    current_step: str | None = None


class CapabilitySource(BaseModel):
    """One paper that contributed evidence for a capability item."""

    model_config = ConfigDict(strict=True)

    pmid: str | None = None
    doi: str | None = None
    title: str
    year: int | None = None


class ProposedEquipment(Equipment):
    sources: list[CapabilitySource] = Field(default_factory=list)
    frequency: int = Field(default=1, ge=1)


class ProposedTechnique(Technique):
    sources: list[CapabilitySource] = Field(default_factory=list)
    frequency: int = Field(default=1, ge=1)


class ProposedExpertise(Expertise):
    sources: list[CapabilitySource] = Field(default_factory=list)
    frequency: int = Field(default=1, ge=1)


class ProposedOrganism(Organism):
    sources: list[CapabilitySource] = Field(default_factory=list)
    frequency: int = Field(default=1, ge=1)


class ProposedReagent(Reagent):
    sources: list[CapabilitySource] = Field(default_factory=list)
    frequency: int = Field(default=1, ge=1)


class ProposedLabState(BaseModel):
    """Aggregated capabilities + per-claim provenance, surfaced for review."""

    model_config = ConfigDict(strict=True)

    equipment: list[ProposedEquipment] = Field(default_factory=list)
    techniques: list[ProposedTechnique] = Field(default_factory=list)
    expertise: list[ProposedExpertise] = Field(default_factory=list)
    organisms: list[ProposedOrganism] = Field(default_factory=list)
    reagents: list[ProposedReagent] = Field(default_factory=list)


class LabStateImportResponse(BaseModel):
    """GET response — full import row state for frontend polling."""

    model_config = ConfigDict(from_attributes=True, strict=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    orcid_id: str
    status: ImportStatus
    progress: ImportProgress
    proposed_state: ProposedLabState | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class AcceptedLabState(BaseModel):
    """The user-trimmed selection — stripped of provenance metadata."""

    model_config = ConfigDict(strict=True)

    equipment: list[Equipment] = Field(default_factory=list, max_length=50)
    techniques: list[Technique] = Field(default_factory=list, max_length=50)
    expertise: list[Expertise] = Field(default_factory=list, max_length=30)
    organisms: list[Organism] = Field(default_factory=list, max_length=20)
    reagents: list[Reagent] = Field(default_factory=list, max_length=50)


class LabStateImportCommit(BaseModel):
    """POST body to commit — caller passes back exactly what they accepted."""

    model_config = ConfigDict(strict=True)

    accepted: AcceptedLabState
