"""Adoption metrics helpers.

Callers record events via `record_event` from input endpoints; the
metrics endpoint aggregates over a rolling window.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adoption_event import AdoptionEvent
from app.schemas.metrics import AdoptionMetricsResponse, EventTypeStats


async def record_event(
    *,
    session: AsyncSession,
    lab_id: uuid.UUID,
    event_type: str,
    user_id: str,
    duration_ms: int | None = None,
    meta: dict[str, Any] | None = None,
) -> AdoptionEvent:
    """Append a single adoption event.

    Non-blocking in the failure sense: the caller should wrap this so
    instrumentation failures never take down an input endpoint.
    """
    event = AdoptionEvent(
        lab_id=lab_id,
        event_type=event_type,
        user_id=user_id,
        duration_ms=duration_ms,
        meta=meta,
    )
    session.add(event)
    await session.flush()
    return event


def _percentile(values: list[int], pct: float) -> float | None:
    """Linear-interpolation percentile; None for empty input."""
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


async def aggregate_metrics(
    *,
    session: AsyncSession,
    lab_id: uuid.UUID,
    window_days: int = 30,
) -> AdoptionMetricsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        await session.execute(
            select(
                AdoptionEvent.event_type,
                AdoptionEvent.duration_ms,
                AdoptionEvent.created_at,
                AdoptionEvent.user_id,
            )
            .where(
                AdoptionEvent.lab_id == lab_id,
                AdoptionEvent.created_at >= since,
            )
            .order_by(AdoptionEvent.created_at.desc())
        )
    ).all()

    # Aggregate in Python: event counts are small (thousands/day) and this
    # keeps the service portable across DBs.
    buckets: dict[str, list[int]] = {}
    for r in rows:
        if r.duration_ms is not None:
            buckets.setdefault(r.event_type, []).append(int(r.duration_ms))
        else:
            buckets.setdefault(r.event_type, [])

    by_type = [
        EventTypeStats(
            event_type=event_type,
            count=len(durations),
            avg_duration_ms=(
                sum(durations) / len(durations) if durations else None
            ),
            p95_duration_ms=_percentile(durations, 0.95),
        )
        for event_type, durations in sorted(buckets.items())
    ]

    recent = [
        {
            "event_type": r.event_type,
            "duration_ms": r.duration_ms,
            "user_id": r.user_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows[:20]
    ]

    # Include total across all events, even those without durations.
    total_count = (
        await session.execute(
            select(func.count())
            .select_from(AdoptionEvent)
            .where(
                AdoptionEvent.lab_id == lab_id,
                AdoptionEvent.created_at >= since,
            )
        )
    ).scalar() or 0

    return AdoptionMetricsResponse(
        since=since,
        total_events=int(total_count),
        by_type=by_type,
        recent=recent,
    )
