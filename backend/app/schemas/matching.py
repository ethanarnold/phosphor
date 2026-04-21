"""Matching schemas - ranked opportunities and gap analysis."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.opportunity import OpportunityResponse

EquipmentStatus = Literal["have", "acquire", "cannot"]
TechniqueStatus = Literal["practiced", "learnable", "gap"]
ExpertiseStatus = Literal["strong", "adjacent", "gap"]


class FeasibilityBreakdown(BaseModel):
    """Per-requirement feasibility tiers for one opportunity."""

    model_config = ConfigDict(strict=True)

    equipment: dict[str, EquipmentStatus] = Field(default_factory=dict)
    techniques: dict[str, TechniqueStatus] = Field(default_factory=dict)
    expertise: dict[str, ExpertiseStatus] = Field(default_factory=dict)


class MatchScore(BaseModel):
    """Composite match score for one opportunity."""

    model_config = ConfigDict(strict=True)

    feasibility: float = Field(..., ge=0.0, le=1.0)
    alignment: float = Field(..., ge=0.0, le=1.0)
    composite: float = Field(..., ge=0.0, le=1.0)
    breakdown: FeasibilityBreakdown


class RankedOpportunity(BaseModel):
    """A scored opportunity as returned by the ranking endpoint."""

    model_config = ConfigDict(from_attributes=True)

    opportunity: OpportunityResponse
    score: MatchScore


class RankedOpportunityList(BaseModel):
    """Paginated list of ranked opportunities."""

    model_config = ConfigDict(strict=True)

    items: list[RankedOpportunity]
    total: int


class GapAnalysis(BaseModel):
    """Analysis of what a lab is missing for a given opportunity."""

    model_config = ConfigDict(strict=True)

    opportunity_id: uuid.UUID
    missing_equipment: list[str] = Field(default_factory=list)
    acquirable_equipment: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    learnable_skills: list[str] = Field(default_factory=list)
    expertise_gaps: list[str] = Field(default_factory=list)
    estimated_effort: Literal["low", "medium", "high"]
    closable_via_collaboration: list[str] = Field(default_factory=list)
