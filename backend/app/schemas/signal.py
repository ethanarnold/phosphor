"""Signal schemas for raw input data."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class ExperimentContent(BaseModel):
    """Content for experiment signal type."""

    model_config = ConfigDict(strict=True)

    date: datetime | None = None
    technique: str = Field(..., min_length=1, max_length=200)
    outcome: Literal["success", "partial", "failed"]
    notes: str = Field(..., min_length=1, max_length=5000)
    equipment_used: list[str] = Field(default_factory=list, max_length=20)
    organisms_used: list[str] = Field(default_factory=list, max_length=10)
    reagents_used: list[str] = Field(default_factory=list, max_length=30)


class DocumentContent(BaseModel):
    """Content for document signal type."""

    model_config = ConfigDict(strict=True)

    filename: str = Field(..., min_length=1, max_length=500)
    document_type: Literal["protocol", "paper", "notes", "other"]
    text_chunks: list[str] = Field(..., min_length=1, max_length=100)
    extracted_equipment: list[str] = Field(default_factory=list, max_length=20)
    extracted_techniques: list[str] = Field(default_factory=list, max_length=20)


class CorrectionContent(BaseModel):
    """Content for user correction signal type."""

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


SignalContent = Annotated[
    Union[ExperimentContent, DocumentContent, CorrectionContent],
    Field(discriminator=None),
]


class SignalCreate(BaseModel):
    """Schema for creating a new signal."""

    model_config = ConfigDict(strict=True)

    signal_type: Literal["experiment", "document", "correction"]
    content: dict[str, Any] = Field(..., description="Signal content based on type")

    def get_typed_content(self) -> ExperimentContent | DocumentContent | CorrectionContent:
        """Parse content based on signal_type."""
        if self.signal_type == "experiment":
            return ExperimentContent.model_validate(self.content)
        elif self.signal_type == "document":
            return DocumentContent.model_validate(self.content)
        elif self.signal_type == "correction":
            return CorrectionContent.model_validate(self.content)
        raise ValueError(f"Unknown signal type: {self.signal_type}")


class SignalResponse(BaseModel):
    """API response for a signal."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    signal_type: str
    content: dict[str, Any]
    processed: bool
    created_at: datetime
    created_by: str


class SignalListResponse(BaseModel):
    """API response for listing signals."""

    model_config = ConfigDict(strict=True)

    signals: list[SignalResponse]
    total: int
