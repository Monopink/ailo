"""Media files enums."""

from enum import IntEnum


class FileType(IntEnum):
    """Media file type classification (media_files.file_type)."""

    AVATAR = 1
    EMOJI = 2
    IMAGE = 3
    DOCUMENT = 4


class FileStatus(IntEnum):
    """Media file status (media_files.status)."""

    ACTIVE = 1
    PENDING = 2
    DELETED = 3


class UploaderType(IntEnum):
    """File uploader type (media_files.upload_by_type)."""

    USER = 1
    ADMIN = 2
    SYSTEM = 3
