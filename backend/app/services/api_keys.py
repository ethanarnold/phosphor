"""API key management service."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_auth import generate_api_key
from app.models.api_key import ApiKey


async def create_api_key(
    session: AsyncSession,
    lab_id: uuid.UUID,
    name: str,
    scopes: dict[str, Any],
    created_by: str,
) -> tuple[ApiKey, str]:
    """Create a new API key for a lab.

    Returns:
        Tuple of (ApiKey model, raw_key string)
    """
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        lab_id=lab_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=scopes,
        created_by=created_by,
    )
    session.add(api_key)
    await session.flush()

    return api_key, raw_key


async def list_api_keys(
    session: AsyncSession,
    lab_id: uuid.UUID,
) -> tuple[list[ApiKey], int]:
    """List all API keys for a lab."""
    count_result = await session.execute(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.lab_id == lab_id)
    )
    total = count_result.scalar() or 0

    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.lab_id == lab_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = list(result.scalars().all())

    return keys, total


async def deactivate_api_key(
    session: AsyncSession,
    lab_id: uuid.UUID,
    key_id: uuid.UUID,
) -> ApiKey | None:
    """Deactivate an API key."""
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.lab_id == lab_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

    api_key.is_active = False
    await session.flush()

    return api_key
