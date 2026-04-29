"""Lab state import model — tracks an in-progress ORCID publication import.

Lifecycle: queued → fetching → extracting → review → committed.
Terminal failure states: failed, cancelled.

The `proposed_state` JSONB holds the aggregated, provenance-tagged extraction
result during the `review` phase. On commit, accepted items flow through the
existing distillation pipeline into a new `lab_states` row, and the proposed
state on this row is preserved as a historical record.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Status values for lab_state_imports.status
IMPORT_STATUS_QUEUED = "queued"
IMPORT_STATUS_FETCHING = "fetching"
IMPORT_STATUS_EXTRACTING = "extracting"
IMPORT_STATUS_REVIEW = "review"
IMPORT_STATUS_COMMITTED = "committed"
IMPORT_STATUS_FAILED = "failed"
IMPORT_STATUS_CANCELLED = "cancelled"


class LabStateImport(Base):
    """One ORCID-driven import attempt scoped to a lab."""

    __tablename__ = "lab_state_imports"

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
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    orcid_id: Mapped[str] = mapped_column(String(19), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{IMPORT_STATUS_QUEUED}'"),
        nullable=False,
        index=True,
    )
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    proposed_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
