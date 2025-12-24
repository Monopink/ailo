"""
Schemas for media upload APIs.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    """Response payload for backend-proxied upload."""

    file_id: str = Field(..., description="File identifier")
    url: str = Field(..., description="Public CDN URL")
    duplicate: bool = Field(False, description="Whether existing file reused")


class MediaAccessResponse(BaseModel):
    """Response for accessing file metadata."""

    file_id: str = Field(..., description="File identifier")
    url: str = Field(..., description="Access URL (public or presigned)")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")
