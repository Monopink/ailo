"""
Storage service package.

Provides provider-agnostic abstractions to manage media files in different
backends (local filesystem, Tencent COS, etc.).
"""

from .base import (
    StorageBackend,
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
)
from .factory import get_storage_backend

__all__ = [
    "StorageBackend",
    "StorageError",
    "StorageNotFoundError",
    "StorageUploadError",
    "get_storage_backend",
]
