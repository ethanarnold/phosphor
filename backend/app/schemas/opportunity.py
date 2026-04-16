"""Opportunity schemas for API validation."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class OpportunityResponse(BaseModel):
    """API response for an opportunity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    description: str
    required_equipment: list[str]
    required_techniques: list[str]
    required_expertise: list[str]
    estimated_complexity: str
    source_paper_ids: list[uuid.UUID]
    quality_score: float | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    """API response for listing opportunities."""

    model_config = ConfigDict(strict=True)

    opportunities: list[OpportunityResponse]
    total: int


class OpportunityStatusUpdate(BaseModel):
    """Schema for updating opportunity status."""

    model_config = ConfigDict(strict=True)

    status: Literal["active", "dismissed", "archived"]
