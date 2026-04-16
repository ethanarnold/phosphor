"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_with_tenant(org_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Get database session with tenant context set for RLS."""
    async with AsyncSessionLocal() as session:
        try:
            # Set the tenant context for row-level security
            # asyncpg doesn't support parameters in SET/SET LOCAL,
            # so we format the value into the query.
            # org_id is from Clerk JWT claims (alphanumeric + underscore),
            # but we sanitize to be safe.
            safe_org_id = org_id.replace("'", "''")
            await session.execute(text(f"SET LOCAL app.current_org_id = '{safe_org_id}'"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection pool."""
    # Test the connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a session with a fresh engine for use in Celery tasks.

    Celery tasks call asyncio.run() which creates a new event loop,
    so the module-level engine (bound to the web server's loop) can't be reused.
    """
    task_engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
    )
    session_factory = async_sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
    await task_engine.dispose()
