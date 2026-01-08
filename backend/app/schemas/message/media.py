"""Media file related schemas.

Defines Pydantic representations aligned with the new object storage model.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import FileStatus, FileType, UploaderType
from app.schemas.common import BaseSchema


class MediaFileBase(BaseSchema):
    """Base media file schema."""

    file_type: FileType = Field(..., description="File type")
    mime_type: str = Field(..., max_length=100, description="MIME type")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    is_public: bool = Field(..., description="Whether file is publicly accessible")


class MediaFileUpload(BaseModel):
    """Schema for media file upload."""

    file_type: FileType = Field(..., description="File type")
    mime_type: str = Field(..., max_length=100, description="MIME type")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    original_name: str = Field(..., max_length=255, description="Original filename")


class MediaFileResponse(MediaFileBase):
    """Schema for media file response data."""

    file_id: str = Field(..., description="External file ID")
    storage_provider: str = Field(..., description="Storage provider identifier")
    bucket_name: str | None = Field(None, description="Bucket name if applicable")
    object_key: str = Field(..., description="Object key within storage backend")
    original_name: str = Field(..., description="Original filename when uploaded")
    file_hash: str | None = Field(None, description="SHA-256 hash for deduplication")
    upload_by_type: UploaderType = Field(..., description="Uploader type")
    upload_by_id: int | None = Field(None, description="Uploader internal ID")
    upload_by_qiao_id: str | None = Field(None, description="Uploader external ID")
    etag: str | None = Field(None, description="Storage provider ETag")
    confirmed_at: datetime | None = Field(None, description="Confirmation timestamp")
    status: FileStatus = Field(..., description="File status")
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Last update time")


class MediaFileListResponse(BaseSchema):
    """Schema for media file list item (minimal info)."""

    file_id: str = Field(..., description="External file ID")
    file_type: FileType = Field(..., description="File type")
    original_name: str = Field(..., description="Original filename")
    object_key: str = Field(..., description="Object key")
    file_size: int = Field(..., description="File size in bytes")
    status: FileStatus = Field(..., description="File status")
    created_at: datetime = Field(..., description="Upload time")


class MediaFileUpdate(BaseModel):
    """Schema for updating media file."""

    status: FileStatus = Field(..., description="New file status")


class MediaFileQuery(BaseModel):
    """Schema for querying media files."""

    file_type: FileType | None = Field(None, description="Filter by file type")
    uploader_qiao_id: str | None = Field(None, description="Filter by uploader")
    status: FileStatus | None = Field(None, description="Filter by status")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records")


class MediaFileStats(BaseSchema):
    """Schema for media file statistics."""

    total_files: int = Field(..., description="Total file count")
    total_size: int = Field(..., description="Total file size in bytes")
    files_by_type: dict[str, int] = Field(..., description="File count by type")
    files_by_status: dict[str, int] = Field(..., description="File count by status")
    avg_file_size: float = Field(..., description="Average file size in bytes")
    storage_usage: str = Field(..., description="Human readable storage usage")
