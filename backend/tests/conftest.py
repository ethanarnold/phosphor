"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import Base, get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app


# Test settings override
def get_test_settings() -> Settings:
    """Get test settings."""
    return Settings(
        database_url="postgresql+asyncpg://phosphor:phosphor@localhost:5432/phosphor_test",  # type: ignore
        redis_url="redis://localhost:6379/1",  # type: ignore
        clerk_secret_key="test_secret",
        anthropic_api_key="test_key",
        environment="test",
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test settings fixture."""
    return get_test_settings()


@pytest_asyncio.fixture
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(
        str(test_settings.database_url),
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncTestSession = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncTestSession() as session:
        # Set tenant context for RLS
        await session.execute(
            text("SET LOCAL app.current_org_id = 'test_org'")
        )
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """Mock authenticated user."""
    return AuthenticatedUser(
        user_id="test_user_123",
        org_id="test_org",
        email="test@example.com",
        roles=["admin"],
    )


@pytest.fixture
def client(mock_user: AuthenticatedUser) -> Generator[TestClient, None, None]:
    """Create test client with mocked auth."""

    def override_get_current_user() -> AuthenticatedUser:
        return mock_user

    def override_get_settings() -> Settings:
        return get_test_settings()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(mock_user: AuthenticatedUser) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""

    def override_get_current_user() -> AuthenticatedUser:
        return mock_user

    def override_get_settings() -> Settings:
        return get_test_settings()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
