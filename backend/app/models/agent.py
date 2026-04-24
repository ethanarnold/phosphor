"""Agent session + message models — persistence for tool-calling runs.

Two tables:

- `agent_sessions` — one row per agent invocation. Tracks lab_id (for RLS),
  user, purpose (so future agents can reuse the table), input, status,
  and final result.
- `agent_messages` — the full message transcript. Assistant tool-call
  requests and their corresponding `role=tool` results are both rows here;
  they reference each other by `tool_name`/`seq` ordering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Status values for agent_sessions.status
AGENT_STATUS_QUEUED = "queued"
AGENT_STATUS_RUNNING = "running"
AGENT_STATUS_COMPLETE = "complete"
AGENT_STATUS_ERROR = "error"

# Purpose values. New agents add to this enum but don't need a migration —
# Postgres stores as VARCHAR, validation lives at the app layer.
AGENT_PURPOSE_REVIEWER = "reviewer"

# Role values for agent_messages.role
MESSAGE_ROLE_SYSTEM = "system"
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_TOOL = "tool"


class AgentSession(Base):
    """One agent invocation, scoped to a lab."""

    __tablename__ = "agent_sessions"

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
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    input_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{AGENT_STATUS_QUEUED}'"),
        nullable=False,
        index=True,
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    final_answer: Mapped[str | None] = mapped_column(String(16000), nullable=True)
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

    messages: Mapped[list[AgentMessage]] = relationship(
        "AgentMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentMessage.seq",
    )


class AgentMessage(Base):
    """A single entry in the agent's message log.

    `seq` is monotonic per session and is the only ordering source. For a
    tool_call round-trip: the assistant message carries `tool_name` +
    `tool_args_json`, and the follow-up row (role=tool) carries the same
    `tool_name` plus `tool_result_json`.
    """

    __tablename__ = "agent_messages"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_agent_messages_session_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(String(32000), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_args_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tool_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    session: Mapped[AgentSession] = relationship("AgentSession", back_populates="messages")
