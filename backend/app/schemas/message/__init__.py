"""
Message system schemas module.

This module imports all message-related Pydantic schemas.
"""

# Message schemas removed - not currently used

# Media schemas
from .media import (
    MediaFileBase,
    MediaFileUpload,
    MediaFileResponse,
    MediaFileListResponse,
    MediaFileUpdate,
    MediaFileQuery,
    MediaFileStats,
)

# Emoticon schemas removed - emoticons table renamed to preset_assets

# Export all message schemas
__all__ = [
    # Media
    "MediaFileBase",
    "MediaFileUpload",
    "MediaFileResponse",
    "MediaFileListResponse",
    "MediaFileUpdate",
    "MediaFileQuery",
    "MediaFileStats",
]
