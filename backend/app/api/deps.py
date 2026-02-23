"""Dependency injection for API routes."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db_with_tenant
from app.core.security import AuthenticatedUser, get_current_user
from app.models.lab import Lab


# Type aliases for common dependencies
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def get_db_session(
    user: CurrentUser,
) -> AsyncSession:
    """Get database session with tenant context from current user."""
    async with get_db_with_tenant(user.org_id) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_lab(
    lab_id: Annotated[uuid.UUID, Path(description="Lab UUID")],
    session: DbSession,
    user: CurrentUser,
) -> Lab:
    """Get the current lab by ID, ensuring tenant isolation.

    Args:
        lab_id: Lab UUID from path
        session: Database session with tenant context
        user: Current authenticated user

    Returns:
        Lab model instance

    Raises:
        HTTPException: If lab not found or access denied
    """
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


CurrentLab = Annotated[Lab, Depends(get_current_lab)]
