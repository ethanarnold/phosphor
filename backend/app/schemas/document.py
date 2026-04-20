"""Document upload & parsing schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClassifiedChunk(BaseModel):
    """A chunk of document text tagged with its classification."""

    model_config = ConfigDict(strict=True)

    text: str = Field(..., min_length=1)
    chunk_type: Literal["methods", "results", "equipment", "protocol", "other"]


class DocumentResponse(BaseModel):
    """Document record response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    filename: str
    content_type: str
    byte_size: int
    status: str
    chunk_count: int
    signal_id: uuid.UUID | None = None
    parse_error: str | None = None
    created_at: datetime
    created_by: str


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    documents: list[DocumentResponse]
    total: int


class ChunkReclassifyRequest(BaseModel):
    """User override for a single chunk classification."""

    model_config = ConfigDict(strict=True)

    chunk_index: int = Field(..., ge=0)
    chunk_type: Literal["methods", "results", "equipment", "protocol", "other"]
