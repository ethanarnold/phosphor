"""Document upload endpoints — Phase 4 input surfaces."""

import time
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentLab, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, require_role
from app.models.document import Document
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.documents import ingest_document
from app.services.metrics import record_event
from app.services.storage import get_file_store

router = APIRouter()

MAX_BYTES = 25 * 1024 * 1024  # 25 MB per file


def _queue_distill(lab_id: str, signal_id: str) -> None:
    from app.tasks.distill import distill_lab_state

    distill_lab_state.delay(lab_id, [signal_id])


async def _handle_upload(
    *,
    file: UploadFile,
    lab_id: uuid.UUID,
    user_id: str,
    session,
) -> Document:
    start = time.perf_counter()
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {MAX_BYTES} bytes",
        )
    store = get_file_store()
    storage_key = await store.put(
        lab_id=str(lab_id),
        filename=file.filename or "unnamed",
        data=data,
    )
    doc = await ingest_document(
        session=session,
        settings=get_settings(),
        lab_id=lab_id,
        created_by=user_id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        storage_key=storage_key,
    )
    if doc.signal_id:
        _queue_distill(str(lab_id), str(doc.signal_id))

    duration_ms = int((time.perf_counter() - start) * 1000)
    try:
        await record_event(
            session=session,
            lab_id=lab_id,
            event_type="document.upload",
            user_id=user_id,
            duration_ms=duration_ms,
            meta={"byte_size": len(data), "status": doc.status},
        )
    except Exception:  # noqa: BLE001 — metrics must not break ingestion
        pass
    return doc


@router.post(
    "/{lab_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> Document:
    """Upload a document, parse it, and emit a document signal."""
    return await _handle_upload(
        file=file,
        lab_id=lab.id,
        user_id=user.user_id,
        session=session,
    )


@router.post(
    "/{lab_id}/documents/bulk",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents_bulk(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    files: list[UploadFile] = File(...),
    _writer: AuthenticatedUser = Depends(require_role(["admin", "researcher"])),
) -> list[Document]:
    """Upload multiple documents at once. Each is parsed independently."""
    out: list[Document] = []
    for f in files:
        doc = await _handle_upload(
            file=f,
            lab_id=lab.id,
            user_id=user.user_id,
            session=session,
        )
        out.append(doc)
    return out


@router.get(
    "/{lab_id}/documents",
    response_model=DocumentListResponse,
)
async def list_documents(
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DocumentListResponse:
    query = select(Document).where(Document.lab_id == lab.id)
    if status_filter:
        query = query.where(Document.status == status_filter)

    total = (
        await session.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    rows = (
        await session.execute(
            query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in rows],
        total=total,
    )


@router.get(
    "/{lab_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: uuid.UUID,
    lab: CurrentLab,
    session: DbSession,
    user: CurrentUser,
) -> Document:
    row = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.lab_id == lab.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return row
