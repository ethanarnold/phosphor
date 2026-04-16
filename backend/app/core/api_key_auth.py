"""API key generation and validation."""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey

API_KEY_PREFIX = "ph_"


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash, key_prefix)
    """
    raw_token = secrets.token_hex(20)
    raw_key = f"{API_KEY_PREFIX}{raw_token}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


async def validate_api_key(
    key: str, session: AsyncSession
) -> ApiKey | None:
    """Validate an API key and return the ApiKey model if valid.

    Also updates last_used_at timestamp.
    """
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        return None

    # Update last_used_at
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(UTC))
    )

    return api_key
