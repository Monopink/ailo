"""
Media file rules derived from system configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.enums import FileType


@dataclass(frozen=True)
class FileTypeRule:
    """Configuration keys for a specific media file type."""

    max_size_key: str
    allowed_mimes_key: str
    daily_quota_key: str
    daily_size_quota_key: str
    is_public: bool


FILE_TYPE_RULES: dict[FileType, FileTypeRule] = {
    FileType.AVATAR: FileTypeRule(
        max_size_key="avatar_max_size_mb",
        allowed_mimes_key="avatar_allowed_formats",
        daily_quota_key="avatar_upload_daily_quota",
        daily_size_quota_key="avatar_upload_daily_size_quota_mb",
        is_public=True,
    ),
    # Other file types (emoji/image/document) intentionally disabled for MVP.
}


def get_file_type_rule(file_type: FileType) -> FileTypeRule | None:
    """Return rule definition or None if unsupported in current stage."""
    return FILE_TYPE_RULES.get(file_type)
