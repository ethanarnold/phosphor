"""File storage abstraction.

Local filesystem backend for dev; a swap-in S3/GCS implementation can
match the same interface later without touching callers.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Protocol


class FileStore(Protocol):
    async def put(self, *, lab_id: str, filename: str, data: bytes) -> str: ...
    async def get(self, storage_key: str) -> bytes: ...


class LocalFileStore:
    """Store files under a local directory keyed by lab_id/uuid_filename."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def put(self, *, lab_id: str, filename: str, data: bytes) -> str:
        lab_dir = self.base_dir / lab_id
        lab_dir.mkdir(parents=True, exist_ok=True)
        key = f"{uuid.uuid4()}_{filename}"
        (lab_dir / key).write_bytes(data)
        return f"{lab_id}/{key}"

    async def get(self, storage_key: str) -> bytes:
        return (self.base_dir / storage_key).read_bytes()


_default_store: FileStore | None = None


def get_file_store(base_dir: str | Path | None = None) -> FileStore:
    """Return a singleton file store. Callers may pass a test dir."""
    global _default_store
    if _default_store is None or base_dir is not None:
        resolved = base_dir or Path(tempfile.gettempdir()) / "phosphor-documents"
        _default_store = LocalFileStore(resolved)
    return _default_store
