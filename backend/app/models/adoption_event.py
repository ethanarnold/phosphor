"""Adoption event model — lightweight event stream for Phase 4 input metrics."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AdoptionEvent(Base):
    """Records time-to-submit and volume for input endpoints.

    Used by the adoption-metrics dashboard to detect friction regressions
    and compressor-starvation warnings (input volume drops).
    """

    __tablename__ = "adoption_events"

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
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Avoid the `metadata` attribute name on SQLAlchemy models — conflicts with
    # Base.metadata. The DB column is still named `metadata` per migration.
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
