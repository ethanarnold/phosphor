"""Lab schemas for API validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LabBase(BaseModel):
    """Base lab schema."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=255)


class LabCreate(LabBase):
    """Schema for creating a lab."""

    pass


class LabResponse(LabBase):
    """Schema for lab response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_org_id: str
    created_at: datetime
    updated_at: datetime
