"""Matching + protocol generation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser, require_role
from app.models.protocol import Protocol
from app.schemas.matching import (
    GapAnalysis,
    RankedOpportunity,
    RankedOpportunityList,
)
from app.schemas.opportunity import OpportunityResponse
from app.schemas.protocol import ProtocolResponse
from app.services.matching import analyze_gaps, rank_opportunities
from app.services.protocols import generate_protocol

router = APIRouter()


@router.get(
    "/{lab_id}/opportunities/ranked",
    response_model=RankedOpportunityList,
)
async def list_ranked_opportunities(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    limit: int = 50,
    min_score: float = 0.0,
    status_filter: str = "active",
) -> RankedOpportunityList:
    """Rank opportunities by feasibility + topical alignment against lab state."""
    try:
        scored = await rank_opportunities(
            session,
            lab,
            limit=limit,
            min_score=min_score,
            status=status_filter,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    items = [
        RankedOpportunity(
            opportunity=OpportunityResponse.model_validate(opp),
            score=score,
        )
        for opp, score in scored
    ]
    return RankedOpportunityList(items=items, total=len(items))


@router.get(
    "/{lab_id}/opportunities/{opp_id}/gaps",
    response_model=GapAnalysis,
)
async def opportunity_gaps(
    opp_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> GapAnalysis:
    """Return the gap analysis for one opportunity against current lab state."""
    try:
        return await analyze_gaps(session, lab, opp_id)
    except ValueError as e:
        detail = str(e)
        code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail or "no state" in detail
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=detail) from e


@router.post(
    "/{lab_id}/opportunities/{opp_id}/protocol",
    response_model=ProtocolResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_protocol(
    request: Request,
    opp_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> Protocol:
    """Generate and persist a protocol for one opportunity."""
    return await generate_protocol(session, lab, opp_id, user.user_id)


@router.get(
    "/{lab_id}/protocols/{protocol_id}",
    response_model=ProtocolResponse,
)
async def get_protocol(
    protocol_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> Protocol:
    """Fetch a persisted protocol."""
    result = await session.execute(
        select(Protocol).where(
            Protocol.id == protocol_id,
            Protocol.lab_id == lab.id,
        )
    )
    protocol = result.scalar_one_or_none()
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")
    return protocol
