"""
Local filesystem storage backend (development/testing use).
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from app.services.storage.base import (
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
)


class LocalStorageBackend(StorageBackend):
    """Store files under a writable directory on local filesystem."""

    def __init__(self, base_path: str, base_url: str) -> None:
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")

    def _resolve_path(self, object_key: str) -> Path:
        file_path = (self.base_path / object_key).resolve()
        if not str(file_path).startswith(str(self.base_path)):
            raise StorageError(f"Invalid object key path traversal attempt: {object_key}")
        return file_path

    def upload(
        self,
        object_key: str,
        file_data: bytes | BinaryIO,
        mime_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        del mime_type, metadata
        path = self._resolve_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if isinstance(file_data, bytes):
                path.write_bytes(file_data)
            else:
                with path.open("wb") as target:
                    shutil.copyfileobj(file_data, target)
        except Exception as exc:  # pragma: no cover - I/O failure
            raise StorageUploadError(f"Failed to upload {object_key}: {exc}") from exc

    def download(self, object_key: str) -> bytes:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise StorageNotFoundError(f"Object not found: {object_key}")
        return path.read_bytes()

    def delete(self, object_key: str) -> None:
        path = self._resolve_path(object_key)
        if path.exists():
            path.unlink()

    def exists(self, object_key: str) -> bool:
        return self._resolve_path(object_key).exists()

    def get_metadata(self, object_key: str) -> dict[str, str]:
        path = self._resolve_path(object_key)
        if not path.exists():
            raise StorageNotFoundError(f"Object not found: {object_key}")
        stat = path.stat()
        return {
            "size": str(stat.st_size),
            "content_type": "application/octet-stream",
            "etag": f'"{stat.st_mtime_ns}"',
            "last_modified": str(stat.st_mtime),
        }

    def get_public_url(self, object_key: str) -> str:
        return f"{self.base_url}/{object_key}"

    def get_presigned_url(
        self,
        object_key: str,
        method: str = "GET",
        expires_in: timedelta = timedelta(minutes=5),
        *,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        del method, expires_in, content_type, content_length
        # Local filesystem does not require presigned URLs
        return self.get_public_url(object_key)
