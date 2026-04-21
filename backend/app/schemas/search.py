"""Search schemas — hybrid keyword + embedding search over past work."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SearchHit(BaseModel):
    """A single search result with provenance."""

    model_config = ConfigDict(strict=True)

    kind: Literal["signal", "paper"]
    id: uuid.UUID
    score: float
    snippet: str
    matched_by: Literal["keyword", "embedding", "both"]
    # Signal-specific
    signal_type: str | None = None
    # Paper-specific
    title: str | None = None
    created_at: datetime


class SearchResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    query: str
    hits: list[SearchHit]
    total: int
