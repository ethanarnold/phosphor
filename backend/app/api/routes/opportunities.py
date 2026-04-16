"""Opportunity browsing and management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.security import AuthenticatedUser, require_role
from app.models.opportunity import Opportunity
from app.schemas.opportunity import (
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityStatusUpdate,
)

router = APIRouter()


@router.get(
    "/{lab_id}/opportunities",
    response_model=OpportunityListResponse,
)
async def list_opportunities(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    status_filter: str | None = None,
    complexity: str | None = None,
    min_quality_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OpportunityListResponse:
    """List extracted opportunities with optional filters."""
    query = select(Opportunity).where(Opportunity.lab_id == lab.id)

    if status_filter is not None:
        query = query.where(Opportunity.status == status_filter)

    if complexity is not None:
        query = query.where(Opportunity.estimated_complexity == complexity)

    if min_quality_score is not None:
        query = query.where(Opportunity.quality_score >= min_quality_score)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Opportunity.quality_score.desc().nullslast()).offset(offset).limit(limit)
    result = await session.execute(query)
    opportunities = result.scalars().all()

    return OpportunityListResponse(
        opportunities=[OpportunityResponse.model_validate(o) for o in opportunities],
        total=total,
    )


@router.get(
    "/{lab_id}/opportunities/{opp_id}",
    response_model=OpportunityResponse,
)
async def get_opportunity(
    opp_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> Opportunity:
    """Get a specific opportunity by ID."""
    result = await session.execute(
        select(Opportunity).where(
            Opportunity.id == opp_id,
            Opportunity.lab_id == lab.id,
        )
    )
    opportunity = result.scalar_one_or_none()

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    return opportunity


@router.patch(
    "/{lab_id}/opportunities/{opp_id}/status",
    response_model=OpportunityResponse,
)
async def update_opportunity_status(
    opp_id: uuid.UUID,
    status_update: OpportunityStatusUpdate,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> Opportunity:
    """Update an opportunity's status (dismiss, archive, reactivate)."""
    result = await session.execute(
        select(Opportunity).where(
            Opportunity.id == opp_id,
            Opportunity.lab_id == lab.id,
        )
    )
    opportunity = result.scalar_one_or_none()

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    opportunity.status = status_update.status
    await session.flush()

    return opportunity
