"""Document parsing + classification service.

Text extraction: plain text and markdown pass through; other formats
return a single stub chunk with parse_error so the route can surface the
limitation. Integrate Unstructured.io here for PDFs/DOCX.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.document import Document
from app.models.signal import RawSignal
from app.schemas.document import ClassifiedChunk

CLASSIFICATION_PROMPT = """You classify paragraphs from research documents.

For each numbered paragraph, return its type from:
- "methods" — experimental procedures
- "results" — findings or data
- "equipment" — instruments, reagents, consumables mentioned
- "protocol" — step-by-step instructions
- "other" — background, discussion, references

Output ONLY a JSON array of strings, one per input paragraph, in the same order.
Example: ["methods", "other", "equipment"]"""

MAX_CHUNKS = 100


def extract_text(*, data: bytes, content_type: str) -> str:
    """Extract plain text from uploaded bytes.

    Plain text and markdown are supported directly. Other types raise to let
    the caller record a parse_error.
    """
    ct = content_type.lower().split(";")[0].strip()
    if ct in {"text/plain", "text/markdown", "text/x-markdown", ""}:
        return data.decode("utf-8", errors="replace")
    raise ValueError(
        f"unsupported content type: {content_type!r} (install Unstructured.io for PDF/DOCX)"
    )


def chunk_text(text: str) -> list[str]:
    """Split on double-newline; collapse whitespace; cap length per chunk."""
    parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    chunks = [p for p in parts if p]
    return chunks[:MAX_CHUNKS]


async def classify_chunks(*, chunks: list[str], settings: Settings) -> list[ClassifiedChunk]:
    """LLM-classify each chunk. Falls back to 'other' on parse errors."""
    if not chunks:
        return []

    numbered = "\n\n".join(f"{i + 1}. {c[:600]}" for i, c in enumerate(chunks))
    response = await acompletion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": CLASSIFICATION_PROMPT},
            {"role": "user", "content": numbered},
        ],
        temperature=0.1,
        max_tokens=400,
    )
    raw = response.choices[0].message.content or "[]"
    try:
        labels: list[str] = json.loads(raw)
    except json.JSONDecodeError:
        labels = []

    allowed = {"methods", "results", "equipment", "protocol", "other"}
    out: list[ClassifiedChunk] = []
    for i, text in enumerate(chunks):
        label = labels[i] if i < len(labels) and labels[i] in allowed else "other"
        out.append(ClassifiedChunk(text=text, chunk_type=label))  # type: ignore[arg-type]
    return out


def _document_signal_content(*, filename: str, chunks: list[ClassifiedChunk]) -> dict[str, Any]:
    """Build DocumentContent-shaped payload for signal ingestion."""
    texts = [c.text for c in chunks]
    equipment = [c.text for c in chunks if c.chunk_type == "equipment"]
    return {
        "filename": filename,
        "document_type": "other",
        "text_chunks": texts or [""],
        "extracted_equipment": equipment[:20],
        "extracted_techniques": [],
    }


async def ingest_document(
    *,
    session: AsyncSession,
    settings: Settings,
    lab_id: uuid.UUID,
    created_by: str,
    filename: str,
    content_type: str,
    data: bytes,
    storage_key: str,
) -> Document:
    """End-to-end: parse → classify → create signal → persist document row."""
    doc = Document(
        lab_id=lab_id,
        filename=filename,
        content_type=content_type,
        byte_size=len(data),
        storage_key=storage_key,
        status="pending",
        chunk_count=0,
        created_by=created_by,
    )
    session.add(doc)
    await session.flush()

    try:
        text = extract_text(data=data, content_type=content_type)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("document contained no extractable text")
        classified = await classify_chunks(chunks=chunks, settings=settings)
    except Exception as exc:  # noqa: BLE001 — record parse error on doc row
        doc.status = "failed"
        doc.parse_error = str(exc)[:2000]
        await session.flush()
        return doc

    signal = RawSignal(
        lab_id=lab_id,
        signal_type="document",
        content=_document_signal_content(filename=filename, chunks=classified),
        created_by=created_by,
    )
    session.add(signal)
    await session.flush()

    doc.signal_id = signal.id
    doc.chunk_count = len(classified)
    doc.status = "parsed"
    await session.flush()
    return doc
