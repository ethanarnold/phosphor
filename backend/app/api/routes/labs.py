"""Lab management endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.lab import Lab
from app.schemas.lab import LabCreate, LabResponse

router = APIRouter()


@router.post(
    "",
    response_model=LabResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lab(
    lab_in: LabCreate,
    session: DbSession,
    user: CurrentUser,
) -> Lab:
    """Create a new lab for the current organization.

    Each organization can have one lab. If a lab already exists for this
    organization, returns 409 Conflict.
    """
    # Check if lab already exists for this org
    result = await session.execute(
        select(Lab).where(Lab.clerk_org_id == user.org_id)
    )
    existing_lab = result.scalar_one_or_none()

    if existing_lab:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lab already exists for this organization",
        )

    lab = Lab(
        clerk_org_id=user.org_id,
        name=lab_in.name,
    )
    session.add(lab)
    await session.flush()

    return lab


@router.get(
    "",
    response_model=LabResponse,
)
async def get_current_lab(
    session: DbSession,
    user: CurrentUser,
) -> Lab:
    """Get the lab for the current organization."""
    result = await session.execute(
        select(Lab).where(Lab.clerk_org_id == user.org_id)
    )
    lab = result.scalar_one_or_none()

    if lab is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No lab found for this organization",
        )

    return lab


@router.get(
    "/{lab_id}",
    response_model=LabResponse,
)
async def get_lab(
    lab_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
) -> Lab:
    """Get a specific lab by ID."""
    result = await session.execute(
        select(Lab).where(
            Lab.id == lab_id,
            Lab.clerk_org_id == user.org_id,
        )
    )
    lab = result.scalar_one_or_none()

    if lab is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab not found",
        )

    return lab
