"""Tests for security utilities."""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import (
    AuthenticatedUser,
    ClerkJWTValidator,
    get_jwt_validator,
    require_role,
)


class TestAuthenticatedUser:
    """Tests for AuthenticatedUser dataclass."""

    def test_create_user_basic(self) -> None:
        """Test creating user with required fields."""
        user = AuthenticatedUser(user_id="user_123", org_id="org_456")
        assert user.user_id == "user_123"
        assert user.org_id == "org_456"
        assert user.email is None
        assert user.roles is None

    def test_create_user_with_all_fields(self) -> None:
        """Test creating user with all fields."""
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            email="test@example.com",
            roles=["admin", "researcher"],
        )
        assert user.user_id == "user_123"
        assert user.org_id == "org_456"
        assert user.email == "test@example.com"
        assert user.roles == ["admin", "researcher"]


class TestRequireRole:
    """Tests for require_role dependency factory."""

    @pytest.mark.asyncio
    async def test_role_checker_with_valid_role(self) -> None:
        """Test role checker allows user with valid role."""
        role_checker = require_role(["admin", "researcher"])
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            roles=["researcher"],
        )
        result = await role_checker(user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_role_checker_with_multiple_valid_roles(self) -> None:
        """Test role checker allows user with one of multiple valid roles."""
        role_checker = require_role(["admin", "researcher", "viewer"])
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            roles=["admin", "viewer"],
        )
        result = await role_checker(user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_role_checker_without_required_role(self) -> None:
        """Test role checker rejects user without required role."""
        role_checker = require_role(["admin"])
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            roles=["viewer"],
        )
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(user=user)
        assert exc_info.value.status_code == 403
        assert "Required roles" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_role_checker_with_no_roles(self) -> None:
        """Test role checker rejects user with no roles."""
        role_checker = require_role(["admin"])
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            roles=None,
        )
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(user=user)
        assert exc_info.value.status_code == 403
        assert "No roles assigned" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_role_checker_with_empty_roles(self) -> None:
        """Test role checker rejects user with empty roles list."""
        role_checker = require_role(["admin"])
        user = AuthenticatedUser(
            user_id="user_123",
            org_id="org_456",
            roles=[],
        )
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(user=user)
        assert exc_info.value.status_code == 403


class TestClerkJWTValidator:
    """Tests for ClerkJWTValidator."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create test settings."""
        return Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",  # type: ignore
            redis_url="redis://localhost:6379/0",  # type: ignore
            clerk_secret_key="test_secret",
            anthropic_api_key="test_key",
        )

    def test_validator_init(self, settings: Settings) -> None:
        """Test validator initialization."""
        validator = ClerkJWTValidator(settings)
        assert validator.settings == settings
        assert validator._jwk_client is None

    def test_validate_token_expired(self, settings: Settings) -> None:
        """Test validation rejects expired tokens."""
        validator = ClerkJWTValidator(settings)

        # Mock the internal _jwk_client
        mock_client = MagicMock()
        mock_key = MagicMock()
        mock_key.key = "fake_key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key
        validator._jwk_client = mock_client

        with patch("app.core.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

            with pytest.raises(HTTPException) as exc_info:
                validator.validate_token("expired_token")

            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail

    def test_validate_token_invalid(self, settings: Settings) -> None:
        """Test validation rejects invalid tokens."""
        validator = ClerkJWTValidator(settings)

        mock_client = MagicMock()
        mock_key = MagicMock()
        mock_key.key = "fake_key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key
        validator._jwk_client = mock_client

        with patch("app.core.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidTokenError("Bad token")

            with pytest.raises(HTTPException) as exc_info:
                validator.validate_token("invalid_token")

            assert exc_info.value.status_code == 401
            assert "Invalid token" in exc_info.value.detail

    def test_validate_token_success(self, settings: Settings) -> None:
        """Test successful token validation."""
        validator = ClerkJWTValidator(settings)

        mock_client = MagicMock()
        mock_key = MagicMock()
        mock_key.key = "fake_key"
        mock_client.get_signing_key_from_jwt.return_value = mock_key
        validator._jwk_client = mock_client

        expected_claims = {"sub": "user_123", "org_id": "org_456", "exp": 9999999999}

        with patch("app.core.security.jwt.decode") as mock_decode:
            mock_decode.return_value = expected_claims

            claims = validator.validate_token("valid_token")
            assert claims == expected_claims


class TestGetJWTValidator:
    """Tests for get_jwt_validator dependency."""

    def test_get_validator_creates_instance(self) -> None:
        """Test get_jwt_validator creates validator instance."""
        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost:5432/test",  # type: ignore
            redis_url="redis://localhost:6379/0",  # type: ignore
            clerk_secret_key="test_secret",
            anthropic_api_key="test_key",
        )

        # Reset global validator
        import app.core.security as security_module
        security_module._validator = None

        validator = get_jwt_validator(settings)
        assert isinstance(validator, ClerkJWTValidator)

        # Second call should return same instance
        validator2 = get_jwt_validator(settings)
        assert validator2 is validator

        # Clean up
        security_module._validator = None
