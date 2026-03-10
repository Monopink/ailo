"""Contact management related schemas.

This module contains Pydantic schemas for contact relationships and requests.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.enums import (
    AvatarDisplayMode,
    ContactRequestSource,
    ContactRequestStatus,
    ContactSource,
    ContactType,
)
from app.schemas.common import BaseSchema

# Contact Schemas


class ContactProfileSummary(BaseSchema):
    """Lightweight profile fields exposed via contact APIs."""

    nickname: str | None = Field(None, description="Contact nickname")
    avatar_url: str | None = Field(None, description="Dynamically generated contact avatar CDN URL")
    gender: int | None = Field(None, description="Gender enum value")
    bio: str | None = Field(None, description="Contact bio")
    region: str | None = Field(None, description="Region information")


class ContactListItem(BaseSchema):
    """List item for contact collections."""

    conversation_id: str = Field(..., description="Conversation identifier")
    contact_qiao_id: str = Field(..., description="Contact external ID")
    alias: str | None = Field(None, description="Contact alias/remark name")
    tags: list[str] = Field(default_factory=list, description="Contact tags")
    is_pinned: bool = Field(..., description="Is pinned to the top")
    is_muted: bool = Field(..., description="Has do-not-disturb enabled")
    is_blocked: bool = Field(..., description="Is blocked by current user")
    avatar_url: str = Field(..., description="Current avatar URL used by contact surfaces")
    remark_avatar_url: str | None = Field(None, description="Custom remark avatar URL")
    original_avatar_url: str = Field(..., description="Original profile avatar URL")
    avatar_display_mode: AvatarDisplayMode = Field(..., description="Avatar display mode")
    profile: ContactProfileSummary = Field(..., description="Contact public profile summary")


class ContactListPagination(BaseSchema):
    """Cursor pagination metadata."""

    cursor: str | None = Field(
        None, description="Opaque cursor for fetching the next page, null when no more data"
    )
    has_more: bool = Field(..., description="Whether additional pages are available")


class ContactListResult(BaseSchema):
    """Paginated contact list response."""

    items: list[ContactListItem] = Field(..., description="Contact list items")
    pagination: ContactListPagination = Field(..., description="Cursor pagination metadata")


class ContactDetailResponse(ContactListItem):
    """Detailed contact info used by detail and mutation endpoints."""

    remark: str | None = Field(None, description="Private remark about this contact")


class ContactCreate(BaseModel):
    """Schema for creating a new contact relationship."""

    contact_type: ContactType = Field(..., description="Contact type")
    contact_qiao_id: str = Field(..., max_length=32, description="Contact external ID")
    alias: str | None = Field(None, max_length=32, description="Contact alias/remark name")
    custom_avatar_key: str | None = Field(
        None,
        max_length=255,
        description="Custom avatar object key (overrides contact's real avatar)",
    )
    custom_avatar_media_id: int | None = Field(
        None, description="FK to media_files.id for audit trail"
    )
    tags: list[str] | None = Field(None, description="Contact tags")
    remark: str | None = Field(None, max_length=400, description="Contact remark/notes")
    source: ContactSource = Field(
        ContactSource.UNKNOWN, description="Contact creation source enum value"
    )


class ContactUpdate(BaseModel):
    """Schema for updating contact information."""

    alias: str | None = Field(None, max_length=32, description="Contact alias/remark name")
    tags: list[str] | None = Field(None, description="Contact tags")
    remark: str | None = Field(None, max_length=400, description="Contact remark/notes")
    avatar_file_id: str | None = Field(
        None,
        description="Custom avatar file ID (file_xxx), null clears current custom avatar",
    )
    avatar_display_mode: AvatarDisplayMode | None = Field(
        None,
        description="Avatar display mode override: 1=original, 2=custom",
    )
    is_pinned: bool | None = Field(None, description="Pin/unpin the contact")
    is_muted: bool | None = Field(None, description="Enable/disable mute")


# Contact Request Schemas


class ContactRequestBase(BaseSchema):
    """Base contact request schema."""

    to_qiao_id: str = Field(..., max_length=32, description="Target external ID")
    message: str | None = Field(None, description="Application message")
    source: ContactRequestSource = Field(..., description="Request source")


class ContactRequestCreate(BaseModel):
    """Schema for creating a contact request."""

    to_qiao_id: str = Field(..., max_length=32, description="Target external ID")
    message: str | None = Field(None, max_length=500, description="Application message")
    alias: str | None = Field(None, max_length=32, description="Contact alias/remark name")
    tags: list[str] | None = Field(None, description="Contact tags")
    source: ContactRequestSource = Field(ContactRequestSource.SEARCH, description="Request source")


class ContactRequestResponse(ContactRequestBase):
    """Schema for contact request response data."""

    from_qiao_id: str = Field(..., description="Applicant external ID")
    from_id: int = Field(..., description="Applicant internal ID")
    to_id: int = Field(..., description="Target internal ID")
    status: ContactRequestStatus = Field(..., description="Request status")
    expires_at: datetime = Field(..., description="Expiration time")
    created_at: datetime = Field(..., description="Request creation time")
    updated_at: datetime = Field(..., description="Last update time")


class ContactRequestWithProfile(BaseSchema):
    """Schema for contact request with applicant profile."""

    id: int = Field(..., description="Request ID")
    from_qiao_id: str = Field(..., description="Applicant external ID")
    message: str | None = Field(None, description="Application message")
    status: ContactRequestStatus = Field(..., description="Request status")
    created_at: datetime = Field(..., description="Request creation time")
    from_profile: ContactProfileSummary = Field(..., description="Applicant profile")


class ContactRequestListResponse(BaseSchema):
    """Schema for contact request list response."""

    items: list[ContactRequestWithProfile] = Field(..., description="Request list")
    pagination: dict[str, Any] = Field(..., description="Pagination info")


class ContactRequestUpdate(BaseModel):
    """Schema for updating contact request status."""

    status: ContactRequestStatus = Field(..., description="New request status")


class ContactRequestAccept(BaseModel):
    """Schema for accepting contact request."""

    alias: str | None = Field(None, max_length=32, description="Contact alias/remark name")
    tags: list[str] | None = Field(None, description="Contact tags")


class ContactRequestRetryPayload(BaseModel):
    """Schema for admin-triggered contact request retry payload."""

    alias: str | None = Field(None, max_length=32, description="Override alias when retry succeeds")
    tags: list[str] | None = Field(None, description="Override tags when retry succeeds")


# Contact Search Schemas


class ContactSearchRequest(BaseModel):
    """Schema for searching contacts."""

    query: str = Field(..., min_length=1, max_length=100, description="Search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class ContactSearchResult(BaseSchema):
    """Schema for contact search result."""

    qiao_id: str = Field(..., description="External ID")
    nickname: str | None = Field(None, description="Display name")
    avatar_url: str | None = Field(
        None, description="Dynamically generated avatar CDN URL (not stored in database)"
    )
    bio: str | None = Field(None, description="Bio description")
    is_contact: bool = Field(..., description="Whether already a contact")


# Batch Operations Schemas


class BatchContactUpdate(BaseModel):
    """Schema for batch updating contacts."""

    contact_qiao_ids: list[str] = Field(
        ..., min_length=1, max_length=50, description="Contact external IDs"
    )
    is_pinned: bool | None = Field(None, description="Pin/unpin contacts")
    is_muted: bool | None = Field(None, description="Mute/unmute contacts")
    is_blocked: bool | None = Field(None, description="Block/unblock contacts")


class BatchContactDelete(BaseModel):
    """Schema for batch deleting contacts."""

    contact_qiao_ids: list[str] = Field(
        ..., min_length=1, max_length=50, description="Contact external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion (cannot be restored)")
