"""
Media file related schemas.

This module contains Pydantic schemas for media file management.
"""

from datetime import datetime

from enums import FileStatus, FileType, UploaderType
from pydantic import BaseModel, Field
from schemas.common import BaseSchema

# Media File Schemas


class MediaFileBase(BaseSchema):
    """Base media file schema."""

    file_type: FileType = Field(..., description="File type")
    original_name: str | None = Field(None, max_length=255, description="Original filename")
    mime_type: str = Field(..., max_length=100, description="MIME type")


class MediaFileUpload(BaseModel):
    """Schema for media file upload."""

    file_type: FileType = Field(..., description="File type")
    original_name: str | None = Field(None, max_length=255, description="Original filename")
    mime_type: str = Field(..., max_length=100, description="MIME type")
    file_size: int = Field(..., gt=0, description="File size in bytes")


class MediaFileResponse(MediaFileBase):
    """Schema for media file response data."""

    file_id: str = Field(..., description="External file ID")
    file_path: str = Field(..., description="File storage path")
    file_url: str = Field(..., description="File access URL")
    file_size: int = Field(..., description="File size in bytes")
    upload_by_type: UploaderType = Field(..., description="Uploader type")
    upload_by_id: int = Field(..., description="Uploader internal ID")
    upload_by_qiao_id: str = Field(..., description="Uploader external ID")
    status: FileStatus = Field(..., description="File status")
    created_at: datetime = Field(..., description="Upload time")
    updated_at: datetime = Field(..., description="Last update time")


class MediaFileListResponse(BaseSchema):
    """Schema for media file list item (minimal info)."""

    file_id: str = Field(..., description="External file ID")
    file_type: FileType = Field(..., description="File type")
    original_name: str | None = Field(None, description="Original filename")
    file_url: str = Field(..., description="File access URL")
    file_size: int = Field(..., description="File size in bytes")
    status: FileStatus = Field(..., description="File status")
    created_at: datetime = Field(..., description="Upload time")


class MediaFileUpdate(BaseModel):
    """Schema for updating media file."""

    status: FileStatus = Field(..., description="New file status")


# Media File Query Schemas


class MediaFileQuery(BaseModel):
    """Schema for querying media files."""

    file_type: FileType | None = Field(None, description="Filter by file type")
    uploader_qiao_id: str | None = Field(None, description="Filter by uploader")
    status: FileStatus | None = Field(None, description="Filter by status")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records")


# Media File Statistics


class MediaFileStats(BaseSchema):
    """Schema for media file statistics."""

    total_files: int = Field(..., description="Total file count")
    total_size: int = Field(..., description="Total file size in bytes")
    files_by_type: dict = Field(..., description="File count by type")
    files_by_status: dict = Field(..., description="File count by status")
    avg_file_size: float = Field(..., description="Average file size in bytes")
    storage_usage: str = Field(..., description="Human readable storage usage")
