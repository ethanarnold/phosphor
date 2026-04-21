"""Adoption metrics endpoint."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.security import AuthenticatedUser, require_role
from app.schemas.metrics import AdoptionMetricsResponse
from app.services.metrics import aggregate_metrics

router = APIRouter()


@router.get(
    "/{lab_id}/metrics/adoption",
    response_model=AdoptionMetricsResponse,
)
async def get_adoption_metrics(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    window_days: int = Query(30, ge=1, le=365),
    _admin: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> AdoptionMetricsResponse:
    """Aggregate adoption-event stats over a rolling window.

    Useful for catching input-friction regressions and compressor
    starvation (input volume drops).
    """
    return await aggregate_metrics(session=session, lab_id=lab.id, window_days=window_days)
