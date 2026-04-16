"""Lab model - represents a research lab (tenant)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    search_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
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
    papers: Mapped[list["Paper"]] = relationship(
        "Paper",
        back_populates="lab",
        lazy="selectin",
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(
        "Opportunity",
        back_populates="lab",
        lazy="selectin",
    )
    literature_scans: Mapped[list["LiteratureScan"]] = relationship(
        "LiteratureScan",
        back_populates="lab",
        lazy="selectin",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey",
        back_populates="lab",
        lazy="selectin",
    )


# Import for type hints (avoid circular imports)
from app.models.api_key import ApiKey
from app.models.distillation import DistillationRun
from app.models.lab_state import LabState
from app.models.literature_scan import LiteratureScan
from app.models.opportunity import Opportunity
from app.models.paper import Paper
from app.models.signal import RawSignal
