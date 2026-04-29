"""Literature scan schemas for API validation."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScanRequest(BaseModel):
    """Schema for triggering a literature scan."""

    model_config = ConfigDict(strict=True)

    query_terms: list[str] = Field(..., min_length=1, max_length=20)
    mesh_terms: list[str] = Field(default_factory=list, max_length=50)
    author_affiliations: list[str] = Field(default_factory=list, max_length=10)
    journals: list[str] = Field(default_factory=list, max_length=20)
    field_of_study: str | None = Field(default=None, max_length=100)
    max_results: int = Field(default=100, ge=1, le=500)
    sources: list[Literal["openalex", "semantic_scholar"]] = Field(
        default=["openalex", "semantic_scholar"]
    )


class ScanResponse(BaseModel):
    """API response for a literature scan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    scan_type: str
    query_params: dict[str, Any]
    papers_found: int
    papers_new: int
    opportunities_extracted: int
    status: str
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    triggered_by: str


class ScanListResponse(BaseModel):
    """API response for listing scans."""

    model_config = ConfigDict(strict=True)

    scans: list[ScanResponse]
    total: int
