"""DistillationRun model - tracks distillation operations."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DistillationRun(Base):
    """Tracks a distillation run (LLM compression operation)."""

    __tablename__ = "distillation_runs"

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
    input_state_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )  # None for initial state
    output_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    signals_processed: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'running', 'completed', 'failed'

    # Relationships
    lab: Mapped["Lab"] = relationship("Lab", back_populates="distillation_runs")


# Import for type hints
from app.models.lab import Lab
