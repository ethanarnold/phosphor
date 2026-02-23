"""LabState model - compressed representation of lab capabilities."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LabState(Base):
    """Compressed representation of lab capabilities (~2K tokens)."""

    __tablename__ = "lab_states"
    __table_args__ = (
        UniqueConstraint("lab_id", "version", name="uq_lab_states_lab_version"),
    )

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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="states")


# Import for type hints
from app.models.lab import Lab
