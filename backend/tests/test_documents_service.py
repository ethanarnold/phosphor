"""Tests for document parsing + classification service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.document import ClassifiedChunk
from app.services.documents import (
    _document_signal_content,
    chunk_text,
    classify_chunks,
    extract_text,
)


def test_extract_text_plain() -> None:
    assert extract_text(data=b"hello world", content_type="text/plain") == "hello world"


def test_extract_text_markdown() -> None:
    assert extract_text(data=b"# hi", content_type="text/markdown") == "# hi"


def test_extract_text_unsupported_raises() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        extract_text(data=b"%PDF-1.4", content_type="application/pdf")


def test_chunk_text_splits_on_blank_lines() -> None:
    text = "Methods:\nran PCR\n\nResults:\nbands at 500bp\n\nEquipment:\nthermal cycler"
    chunks = chunk_text(text)
    assert len(chunks) == 3
    assert "PCR" in chunks[0]


def test_chunk_text_empty_returns_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("\n\n\n") == []


@pytest.mark.asyncio
async def test_classify_chunks_falls_back_to_other_on_bad_json(test_settings) -> None:  # type: ignore[no-untyped-def]
    class _Msg:
        content = "not json"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    with patch(
        "app.services.documents.acompletion",
        new=AsyncMock(return_value=_Resp()),
    ):
        out = await classify_chunks(chunks=["abc", "def"], settings=test_settings)

    assert len(out) == 2
    assert all(c.chunk_type == "other" for c in out)


def test_document_signal_content_collects_equipment() -> None:
    chunks = [
        ClassifiedChunk(text="thermal cycler", chunk_type="equipment"),
        ClassifiedChunk(text="ran qPCR", chunk_type="methods"),
    ]
    payload = _document_signal_content(filename="note.md", chunks=chunks)
    assert payload["filename"] == "note.md"
    assert "thermal cycler" in payload["extracted_equipment"]
    assert len(payload["text_chunks"]) == 2
