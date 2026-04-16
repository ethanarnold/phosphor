"""Paper model - literature stored from PubMed/Semantic Scholar."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Paper(Base):
    """A paper ingested from literature APIs."""

    __tablename__ = "papers"

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
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    pmid: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    semantic_scholar_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    journal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mesh_terms: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
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
    lab: Mapped["Lab"] = relationship("Lab", back_populates="papers")


# Import for type hints
from app.models.lab import Lab  # noqa: E402
