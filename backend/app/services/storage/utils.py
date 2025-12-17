"""
Utilities for storage operations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.utils.snowflake import generate_snowflake_id

FILE_TYPE_PREFIX = {
    1: "avatars",
    2: "emojis",
    3: "images",
    4: "documents",
}


def get_extension_from_mime(mime_type: str) -> str:
    """Return file extension (without dot) for provided MIME type."""
    normalized = mime_type.lower()
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
        "application/pdf": "pdf",
    }
    return mapping.get(normalized, "bin")


def generate_object_key(file_type: int, mime_type: str) -> str:
    """Generate object key following {type}/{year}/{month}/{snowflake}.{ext} format."""
    now = datetime.now(UTC)
    snowflake_id = generate_snowflake_id()
    prefix = FILE_TYPE_PREFIX.get(file_type, "files")
    extension = get_extension_from_mime(mime_type)
    return f"{prefix}/{now.year}/{now.month:02d}/{snowflake_id}.{extension}"


def generate_file_id() -> str:
    """Generate external file identifier."""
    return f"file_{generate_snowflake_id()}"
