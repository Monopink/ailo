"""
Schemas for media upload APIs.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import FileType


class UploadTokenRequest(BaseModel):
    """Request body for upload-token endpoint."""

    file_type: FileType = Field(..., description="File type identifier")
    mime_type: str = Field(..., min_length=3, max_length=100, description="MIME type")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    file_hash: str | None = Field(
        None,
        min_length=32,
        max_length=128,
        description="Optional SHA-256 hash (hex)",
    )
    original_name: str | None = Field(
        None, max_length=255, description="Optional original filename"
    )


class UploadTokenResponse(BaseModel):
    """Response for upload-token endpoint."""

    file_id: str = Field(..., description="File identifier")
    upload_url: str | None = Field(None, description="Pre-signed upload URL (PUT)")
    object_key: str | None = Field(None, description="Object key for direct upload")
    expires_in: int | None = Field(None, description="Upload URL expiration (seconds)")
    url: str | None = Field(None, description="Existing file URL when deduplicated")
    duplicate: bool = Field(False, description="Whether upload was deduplicated")


class UploadConfirmRequest(BaseModel):
    """Request body for upload-confirm endpoint."""

    file_id: str = Field(..., min_length=10, description="File identifier to confirm")
    etag: str | None = Field(None, max_length=128, description="ETag returned by COS")


class UploadConfirmResponse(BaseModel):
    """Response for upload confirmation."""

    file_id: str = Field(..., description="File identifier")
    url: str = Field(..., description="Public URL for the file")
    duplicate: bool = Field(False, description="Whether existing file reused")


class MediaAccessResponse(BaseModel):
    """Response for accessing file metadata."""

    file_id: str = Field(..., description="File identifier")
    url: str = Field(..., description="Access URL (public or presigned)")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")
