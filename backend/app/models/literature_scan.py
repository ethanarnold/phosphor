"""LiteratureScan model - tracks literature scan jobs."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LiteratureScan(Base):
    """Tracks a literature scan and extraction job."""

    __tablename__ = "literature_scans"

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
    scan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    query_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    papers_found: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    papers_new: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    opportunities_extracted: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="literature_scans")


# Import for type hints
from app.models.lab import Lab  # noqa: E402
