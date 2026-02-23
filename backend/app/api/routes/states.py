"""Lab state retrieval endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.models.lab_state import LabState
from app.schemas.lab_state import (
    LabStateData,
    LabStateHistoryResponse,
    LabStateResponse,
)

router = APIRouter()


@router.get(
    "/{lab_id}/state",
    response_model=LabStateResponse,
)
async def get_current_state(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabState:
    """Get the current (latest version) lab state.

    Returns the most recent compressed representation of the lab's
    capabilities, techniques, and experimental history.
    """
    result = await session.execute(
        select(LabState)
        .where(LabState.lab_id == lab.id)
        .order_by(LabState.version.desc())
        .limit(1)
    )
    state = result.scalar_one_or_none()

    if state is None:
        # Return empty state for new labs
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No state found. Submit signals to generate initial state.",
        )

    return state


@router.get(
    "/{lab_id}/state/history",
    response_model=LabStateHistoryResponse,
)
async def get_state_history(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    limit: int = 10,
    offset: int = 0,
) -> LabStateHistoryResponse:
    """Get historical versions of the lab state.

    Returns a paginated list of previous lab state versions, ordered by
    version descending (newest first).
    """
    # Get total count
    count_result = await session.execute(
        select(func.count()).where(LabState.lab_id == lab.id)
    )
    total = count_result.scalar() or 0

    # Get paginated results
    result = await session.execute(
        select(LabState)
        .where(LabState.lab_id == lab.id)
        .order_by(LabState.version.desc())
        .offset(offset)
        .limit(limit)
    )
    states = result.scalars().all()

    return LabStateHistoryResponse(
        states=[LabStateResponse.model_validate(s) for s in states],
        total=total,
    )


@router.get(
    "/{lab_id}/state/versions/{version}",
    response_model=LabStateResponse,
)
async def get_state_version(
    version: int,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> LabState:
    """Get a specific version of the lab state."""
    result = await session.execute(
        select(LabState).where(
            LabState.lab_id == lab.id,
            LabState.version == version,
        )
    )
    state = result.scalar_one_or_none()

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State version {version} not found",
        )

    return state
