"""
Helpers for generating media URLs.
"""

from __future__ import annotations

from datetime import timedelta

from app.models.message import MediaFile
from app.services.storage.factory import get_storage_backend


def build_public_url(media_file: MediaFile) -> str:
    """Return permanent URL for a media file."""
    if media_file.cdn_domain:
        base = media_file.cdn_domain.rstrip("/")
        return f"{base}/{media_file.object_key}"

    backend = get_storage_backend()
    return backend.get_public_url(media_file.object_key)


def build_private_url(media_file: MediaFile, *, expires_in: int = 3600) -> str:
    """Return presigned URL for private media files."""
    backend = get_storage_backend()
    return backend.get_presigned_url(
        media_file.object_key,
        method="GET",
        expires_in=timedelta(seconds=expires_in),
    )
