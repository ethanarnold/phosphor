"""Feedback schemas — opportunity decisions + inline state corrections."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OpportunityFeedback(BaseModel):
    """Accept/reject an opportunity in one click."""

    model_config = ConfigDict(strict=True)

    decision: Literal["accept", "reject"]
    reason: str | None = Field(default=None, max_length=1000)


class StateCorrection(BaseModel):
    """Inline correction to a field in the current lab state."""

    model_config = ConfigDict(strict=True)

    correction_type: Literal["add", "remove", "update"]
    field: Literal[
        "equipment",
        "techniques",
        "expertise",
        "organisms",
        "reagents",
        "resource_constraints",
    ]
    item_name: str = Field(..., min_length=1, max_length=200)
    new_value: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    """What the user changed + the signal we emitted (for undo/visibility)."""

    model_config = ConfigDict(strict=True)

    signal_id: uuid.UUID
    correction: StateCorrection | None = None
    opportunity_id: uuid.UUID | None = None
    decision: Literal["accept", "reject"] | None = None
    created_at: datetime
