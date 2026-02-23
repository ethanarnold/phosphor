"""Lab model - represents a research lab (tenant)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Lab(Base):
    """Represents a research lab (tenant) in the system."""

    __tablename__ = "labs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    clerk_org_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    states: Mapped[list["LabState"]] = relationship(
        "LabState",
        back_populates="lab",
        lazy="selectin",
    )
    signals: Mapped[list["RawSignal"]] = relationship(
        "RawSignal",
        back_populates="lab",
        lazy="selectin",
    )
    distillation_runs: Mapped[list["DistillationRun"]] = relationship(
        "DistillationRun",
        back_populates="lab",
        lazy="selectin",
    )


# Import for type hints (avoid circular imports)
from app.models.distillation import DistillationRun
from app.models.lab_state import LabState
from app.models.signal import RawSignal
