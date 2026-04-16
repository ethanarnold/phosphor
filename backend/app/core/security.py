"""Security utilities - Clerk JWT validation and authentication."""

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

security_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user from Clerk JWT."""

    user_id: str
    org_id: str
    email: str | None = None
    roles: list[str] | None = None


class ClerkJWTValidator:
    """Validates Clerk JWTs using JWKS."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwk_client: PyJWKClient | None = None

    @property
    def jwk_client(self) -> PyJWKClient:
        """Lazy-load JWKS client."""
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(self.settings.clerk_jwks_url)
        return self._jwk_client

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate JWT and return claims.

        Args:
            token: JWT token string (without Bearer prefix)

        Returns:
            Decoded JWT claims

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Get signing key from JWKS
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)

            # Decode and validate
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_exp": True,
                    "verify_iat": True,
                },
            )
            return claims

        except jwt.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e


# Singleton validator instance
_validator: ClerkJWTValidator | None = None


def get_jwt_validator(settings: Settings = Depends(get_settings)) -> ClerkJWTValidator:
    """Get or create JWT validator instance."""
    global _validator
    if _validator is None:
        _validator = ClerkJWTValidator(settings)
    return _validator


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    validator: ClerkJWTValidator = Depends(get_jwt_validator),
) -> AuthenticatedUser:
    """Extract and validate current user from JWT or API key.

    Checks Bearer token first, then falls back to X-API-Key header.

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        validator: JWT validator instance

    Returns:
        AuthenticatedUser with user details

    Raises:
        HTTPException: If not authenticated or invalid token
    """
    # Try Bearer token first
    if credentials is not None:
        claims = validator.validate_token(credentials.credentials)

        user_id = claims.get("sub")
        org_id = claims.get("org_id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )

        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization context required",
            )

        return AuthenticatedUser(
            user_id=user_id,
            org_id=org_id,
            email=claims.get("email"),
            roles=claims.get("org_role", []),
        )

    # Fall back to X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        from app.core.api_key_auth import validate_api_key
        from app.core.database import AsyncSessionLocal
        from app.models.lab import Lab

        async with AsyncSessionLocal() as session:
            api_key = await validate_api_key(api_key_header, session)
            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API key",
                )

            # Look up the lab to get org_id
            from sqlalchemy import select

            lab_result = await session.execute(
                select(Lab).where(Lab.id == api_key.lab_id)
            )
            lab = lab_result.scalar_one_or_none()
            if lab is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key lab not found",
                )

            await session.commit()

            # Derive roles from scopes
            roles = ["api_key"]
            if api_key.scopes.get("admin"):
                roles.append("admin")
            if api_key.scopes.get("researcher") or api_key.scopes.get("literature:scan"):
                roles.append("researcher")

            return AuthenticatedUser(
                user_id=f"apikey:{api_key.key_prefix}",
                org_id=lab.clerk_org_id,
                email=None,
                roles=roles,
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(required_roles: list[str]) -> Any:
    """Dependency factory for role-based access control.

    Args:
        required_roles: List of roles that can access the endpoint

    Returns:
        Dependency function that validates roles
    """

    async def role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user.roles is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No roles assigned",
            )

        if not any(role in required_roles for role in user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {required_roles}",
            )

        return user

    return role_checker
