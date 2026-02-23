"""Application configuration with Pydantic settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
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

    @property
    def database_url_sync(self) -> str:
        """Convert async URL to sync for Alembic."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
