"""API key schemas for validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=255)
    scopes: dict[str, bool] = Field(
        ...,
        description="Permission scopes, e.g. {'literature:scan': true, 'opportunities:read': true}",
    )


class ApiKeyCreateResponse(BaseModel):
    """One-time response with the plaintext API key."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    name: str
    key: str = Field(description="Plaintext API key (shown only once)")
    key_prefix: str
    scopes: dict[str, Any]
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """API response for an API key (no plaintext key)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    name: str
    key_prefix: str
    scopes: dict[str, Any]
    is_active: bool
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    """API response for listing API keys."""

    model_config = ConfigDict(strict=True)

    keys: list[ApiKeyResponse]
    total: int
