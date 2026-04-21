"""Application configuration with Pydantic settings."""

import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database
    database_url: PostgresDsn

    # Redis
    redis_url: RedisDsn

    @field_validator("database_url", mode="before")
    @classmethod
    def _force_asyncpg_driver(cls, v: Any) -> Any:
        # Railway/Heroku-style URLs come as `postgresql://` or `postgres://`.
        # The async engine needs the `+asyncpg` driver tag; Alembic strips it
        # via `database_url_sync`, so forcing it here is safe for both paths.
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = "postgresql://" + v[len("postgres://") :]
            if v.startswith("postgresql://"):
                v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    # Clerk
    clerk_secret_key: str
    clerk_jwks_url: str = "https://api.clerk.com/v1/jwks"
    clerk_issuer: str = "https://clerk.com"

    # Anthropic (via LiteLLM)
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-4-20250514"

    # Distillation
    max_state_tokens: int = 2000
    distillation_batch_size: int = 10

    # Literature ingestion
    pubmed_api_key: str | None = None
    semantic_scholar_api_key: str | None = None
    literature_scan_max_results: int = 200

    # Embeddings
    embedding_model: str = "text-embedding-3-small"

    @property
    def database_url_sync(self) -> str:
        """Convert async URL to sync for Alembic."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    # Export secrets that third-party libraries read directly from the
    # environment (LiteLLM reads `os.environ["ANTHROPIC_API_KEY"]` rather
    # than our Settings object). Without this, processes like uvicorn that
    # don't inherit the shell's exported env fail to authenticate with the
    # LLM provider even though .env was loaded into Settings.
    _export_env_for_third_party(settings)
    return settings


def _export_env_for_third_party(settings: "Settings") -> None:
    """Copy Settings values into os.environ for libs that read env directly.

    Only overwrites unset keys so an explicit shell export always wins.
    """
    pairs = {
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
    }
    for key, value in pairs.items():
        if value and not os.environ.get(key):
            os.environ[key] = value
