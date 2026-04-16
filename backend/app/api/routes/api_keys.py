"""API key management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.security import AuthenticatedUser, require_role
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.services.api_keys import (
    create_api_key,
    deactivate_api_key,
    list_api_keys,
)

router = APIRouter()


@router.post(
    "/{lab_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    key_in: ApiKeyCreate,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _admin: AuthenticatedUser = Depends(require_role(["admin"])),
) -> dict:
    """Create a new API key for programmatic access.

    The plaintext key is returned only once in this response.
    Store it securely.
    """
    api_key, raw_key = await create_api_key(
        session=session,
        lab_id=lab.id,
        name=key_in.name,
        scopes=key_in.scopes,
        created_by=user.user_id,
    )

    return {
        "id": api_key.id,
        "lab_id": api_key.lab_id,
        "name": api_key.name,
        "key": raw_key,
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "created_at": api_key.created_at,
    }


@router.get(
    "/{lab_id}/api-keys",
    response_model=ApiKeyListResponse,
)
async def list_keys(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _admin: AuthenticatedUser = Depends(require_role(["admin"])),
) -> ApiKeyListResponse:
    """List all API keys for a lab (no plaintext keys shown)."""
    keys, total = await list_api_keys(session, lab.id)

    return ApiKeyListResponse(
        keys=[ApiKeyResponse.model_validate(k) for k in keys],
        total=total,
    )


@router.delete(
    "/{lab_id}/api-keys/{key_id}",
    response_model=ApiKeyResponse,
)
async def delete_key(
    key_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    _admin: AuthenticatedUser = Depends(require_role(["admin"])),
) -> ApiKeyResponse:
    """Deactivate an API key."""
    api_key = await deactivate_api_key(session, lab.id, key_id)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    return ApiKeyResponse.model_validate(api_key)
