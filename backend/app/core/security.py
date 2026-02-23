"""Security utilities - Clerk JWT validation and authentication."""

from dataclasses import dataclass
from typing import Any

import httpx
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

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )


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
    """Extract and validate current user from JWT.

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        validator: JWT validator instance

    Returns:
        AuthenticatedUser with user details

    Raises:
        HTTPException: If not authenticated or invalid token
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = validator.validate_token(credentials.credentials)

    # Extract user info from Clerk claims
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
