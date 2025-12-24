"""
Abstract storage backend definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import BinaryIO


class StorageError(Exception):
    """Base exception for storage operations."""


class StorageNotFoundError(StorageError):
    """Raised when storage object cannot be located."""


class StorageUploadError(StorageError):
    """Raised when storage upload fails."""


class StorageBackend(ABC):
    """Abstract interface for storage backends."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier for the storage backend."""

    @abstractmethod
    def upload(
        self,
        object_key: str,
        file_data: bytes | BinaryIO,
        mime_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Upload binary data to the storage backend."""

    @abstractmethod
    def download(self, object_key: str) -> bytes:
        """Download binary data from storage."""

    @abstractmethod
    def delete(self, object_key: str) -> None:
        """Delete object from storage."""

    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """Return True if object exists, False otherwise."""

    @abstractmethod
    def get_metadata(self, object_key: str) -> dict[str, str]:
        """Return metadata information about stored object."""

    @abstractmethod
    def get_public_url(self, object_key: str) -> str:
        """Return permanent CDN/public URL for stored object."""

    @abstractmethod
    def get_presigned_url(
        self,
        object_key: str,
        method: str = "GET",
        expires_in: timedelta = timedelta(minutes=5),
        *,
        content_type: str | None = None,
        content_length: int | None = None,
    ) -> str:
        """Return presigned URL for temporal access."""
