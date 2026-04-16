"""Opportunity model - research opportunities extracted from literature."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Opportunity(Base):
    """A concrete research opportunity extracted from literature."""

    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    lab_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_equipment: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    required_techniques: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    required_expertise: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    estimated_complexity: Mapped[str] = mapped_column(String(20), nullable=False)
    source_paper_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
    )
    extraction_prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'active'"),
        nullable=False,
        index=True,
    )
    # embedding column is managed via raw SQL (pgvector Vector type)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="opportunities")


# Import for type hints
from app.models.lab import Lab  # noqa: E402
