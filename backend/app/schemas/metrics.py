"""Adoption metrics schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventTypeStats(BaseModel):
    model_config = ConfigDict(strict=True)

    event_type: str
    count: int
    avg_duration_ms: float | None = None
    p95_duration_ms: float | None = None


class AdoptionMetricsResponse(BaseModel):
    """Rolling-window metrics for the adoption dashboard."""

    model_config = ConfigDict(strict=True)

    since: datetime
    total_events: int
    by_type: list[EventTypeStats]
    recent: list[dict[str, Any]]
