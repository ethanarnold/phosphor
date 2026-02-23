"""RawSignal model - incoming data to be distilled into lab state."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RawSignal(Base):
    """Raw signal input to be processed by the distillation engine."""

    __tablename__ = "raw_signals"

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
    signal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'experiment', 'document', 'correction'
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="signals")


# Import for type hints
from app.models.lab import Lab
