"""Paper schemas for API validation."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaperResponse(BaseModel):
    """API response for a paper."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    doi: str | None = None
    pmid: str | None = None
    semantic_scholar_id: str | None = None
    title: str
    abstract: str = Field(description="Full abstract text")
    authors: list[dict[str, Any]] | None = None
    journal: str | None = None
    publication_date: date | None = None
    source: str
    created_at: datetime


class PaperListResponse(BaseModel):
    """API response for listing papers."""

    model_config = ConfigDict(strict=True)

    papers: list[PaperResponse]
    total: int
