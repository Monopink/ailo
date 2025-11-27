"""
Contact management related schemas.

This module contains Pydantic schemas for contact relationships and requests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from enums import ContactRequestSource, ContactRequestStatus, ContactType
from pydantic import BaseModel, Field
from schemas.common import BaseSchema

# Contact Schemas


class ContactBase(BaseSchema):
    """Base contact schema with common fields."""

    contact_type: ContactType = Field(..., description="Contact type")
    contact_qiao_id: str = Field(..., max_length=32, description="Contact external ID")
    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    custom_avatar_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, max_length=500, description="Contact remark/notes")


class ContactCreate(BaseModel):
    """Schema for creating a new contact relationship."""

    contact_type: ContactType = Field(..., description="Contact type")
    contact_qiao_id: str = Field(..., max_length=32, description="Contact external ID")
    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    custom_avatar_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, max_length=500, description="Contact remark/notes")
    source: Optional[str] = Field(
        "unknown", max_length=32, description="Contact creation source identifier"
    )


class ContactUpdate(BaseModel):
    """Schema for updating contact information."""

    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    custom_avatar_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, max_length=500, description="Contact remark/notes")
    is_pinned: Optional[bool] = Field(None, description="Is pinned")
    is_muted: Optional[bool] = Field(None, description="Is muted")
    is_blocked: Optional[bool] = Field(None, description="Is blocked")


class ContactResponse(ContactBase):
    """Schema for contact response data."""

    conv_id: str = Field(..., description="Conversation identifier")
    im_conv_id: str = Field(..., description="IM provider conversation ID")
    contact_id: int = Field(..., description="Contact internal ID")
    is_pinned: bool = Field(..., description="Is pinned")
    is_muted: bool = Field(..., description="Is muted")
    is_blocked: bool = Field(..., description="Is blocked")
    is_deleted: bool = Field(..., description="Is deleted")
    source: str = Field(..., description="Contact creation source identifier")
    created_at: datetime = Field(..., description="Contact creation time")
    updated_at: datetime = Field(..., description="Last update time")


class ContactListResponse(BaseSchema):
    """Schema for contact list item (minimal info)."""

    conv_id: str = Field(..., description="Conversation identifier")
    im_conv_id: str = Field(..., description="IM provider conversation ID")
    contact_qiao_id: str = Field(..., description="Contact external ID")
    contact_type: ContactType = Field(..., description="Contact type")
    alias: Optional[str] = Field(None, description="Contact alias/remark name")
    custom_avatar_url: Optional[str] = Field(None, description="Custom avatar URL")
    is_pinned: bool = Field(..., description="Is pinned")
    is_muted: bool = Field(..., description="Is muted")
    is_blocked: bool = Field(..., description="Is blocked")
    source: str = Field(..., description="Contact creation source identifier")
    created_at: datetime = Field(..., description="Contact creation time")
    # Profile fields
    nickname: Optional[str] = Field(None, description="Contact nickname from profile")
    avatar_url: Optional[str] = Field(None, description="Contact avatar URL from profile")
    bio: Optional[str] = Field(None, description="Contact bio from profile")
    gender: Optional[int] = Field(None, description="Contact gender from profile")


# Conversation Info Schema


class ContactInfoBase(BaseSchema):
    """Base schema for contact info in conversation."""

    nickname: Optional[str] = Field(None, description="Contact nickname")
    avatar_url: Optional[str] = Field(None, description="Contact avatar URL")
    gender: Optional[int] = Field(None, description="Contact gender")


class ConversationInfoResponse(BaseSchema):
    """Schema for conversation info response."""

    conv_id: str = Field(..., description="Conversation identifier")
    im_conv_id: str = Field(..., description="IM provider conversation ID")
    contact_qiao_id: str = Field(..., description="Contact external ID")
    contact_type: ContactType = Field(..., description="Contact type")
    contact_info: ContactInfoBase = Field(..., description="Contact basic info")


# Contact Request Schemas


class ContactRequestBase(BaseSchema):
    """Base contact request schema."""

    to_qiao_id: str = Field(..., max_length=32, description="Target external ID")
    to_type: ContactType = Field(..., description="Target type")
    message: Optional[str] = Field(None, description="Application message")
    source: ContactRequestSource = Field(..., description="Request source")


class ContactRequestCreate(BaseModel):
    """Schema for creating a contact request."""

    to_qiao_id: str = Field(..., max_length=32, description="Target external ID")
    message: Optional[str] = Field(None, max_length=500, description="Application message")
    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    tags: Optional[List[str]] = Field(None, description="Contact tags")
    source: ContactRequestSource = Field(ContactRequestSource.SEARCH, description="Request source")


class ContactRequestResponse(ContactRequestBase):
    """Schema for contact request response data."""

    from_qiao_id: str = Field(..., description="Applicant external ID")
    from_type: ContactType = Field(..., description="Applicant type")
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
    from_type: ContactType = Field(..., description="Applicant type")
    message: Optional[str] = Field(None, description="Application message")
    status: ContactRequestStatus = Field(..., description="Request status")
    created_at: datetime = Field(..., description="Request creation time")
    from_profile: ContactInfoBase = Field(..., description="Applicant profile")


class ContactRequestListResponse(BaseSchema):
    """Schema for contact request list response."""

    items: List[ContactRequestWithProfile] = Field(..., description="Request list")
    pagination: dict = Field(..., description="Pagination info")


class ContactRequestUpdate(BaseModel):
    """Schema for updating contact request status."""

    status: ContactRequestStatus = Field(..., description="New request status")


class ContactRequestAccept(BaseModel):
    """Schema for accepting contact request."""

    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    tags: Optional[List[str]] = Field(None, description="Contact tags")


# Contact Search Schemas


class ContactSearchRequest(BaseModel):
    """Schema for searching contacts."""

    query: str = Field(..., min_length=1, max_length=100, description="Search query")
    contact_type: Optional[ContactType] = Field(None, description="Filter by contact type")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class ContactSearchResult(BaseSchema):
    """Schema for contact search result."""

    qiao_id: str = Field(..., description="External ID")
    contact_type: ContactType = Field(..., description="Contact type")
    nickname: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio description")
    is_contact: bool = Field(..., description="Whether already a contact")


# Batch Operations Schemas


class BatchContactUpdate(BaseModel):
    """Schema for batch updating contacts."""

    contact_qiao_ids: List[str] = Field(
        ..., min_length=1, max_length=50, description="Contact external IDs"
    )
    is_pinned: Optional[bool] = Field(None, description="Pin/unpin contacts")
    is_muted: Optional[bool] = Field(None, description="Mute/unmute contacts")
    is_blocked: Optional[bool] = Field(None, description="Block/unblock contacts")


class BatchContactDelete(BaseModel):
    """Schema for batch deleting contacts."""

    contact_qiao_ids: List[str] = Field(
        ..., min_length=1, max_length=50, description="Contact external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion (cannot be restored)")
