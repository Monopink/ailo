"""
Contact management related schemas.

This module contains Pydantic schemas for contact relationships and requests.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from enums import ContactType, ContactRequestSource, ContactRequestStatus
from schemas.common import BaseSchema


# Contact Schemas


class ContactBase(BaseSchema):
    """Base contact schema with common fields."""

    contact_type: ContactType = Field(..., description="Contact type")
    contact_qiao_id: str = Field(..., max_length=32, description="Contact external ID")
    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    avatar_alias_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, description="Contact remark/notes")


class ContactCreate(BaseModel):
    """Schema for creating a new contact relationship."""

    contact_type: ContactType = Field(..., description="Contact type")
    contact_qiao_id: str = Field(..., max_length=32, description="Contact external ID")
    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    avatar_alias_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, description="Contact remark/notes")


class ContactUpdate(BaseModel):
    """Schema for updating contact information."""

    alias: Optional[str] = Field(None, max_length=100, description="Contact alias/remark name")
    avatar_alias_url: Optional[str] = Field(None, max_length=500, description="Custom avatar URL")
    tags: Optional[Dict[str, Any]] = Field(None, description="Contact tags (JSONB)")
    remark: Optional[str] = Field(None, description="Contact remark/notes")
    is_pinned: Optional[bool] = Field(None, description="Is pinned")
    is_muted: Optional[bool] = Field(None, description="Is muted")
    is_blocked: Optional[bool] = Field(None, description="Is blocked")


class ContactResponse(ContactBase):
    """Schema for contact response data."""

    conv_id: str = Field(..., description="Conversation identifier")
    contact_id: int = Field(..., description="Contact internal ID")
    is_pinned: bool = Field(..., description="Is pinned")
    is_muted: bool = Field(..., description="Is muted")
    is_blocked: bool = Field(..., description="Is blocked")
    is_deleted: bool = Field(..., description="Is deleted")
    created_at: datetime = Field(..., description="Contact creation time")
    updated_at: datetime = Field(..., description="Last update time")


class ContactListResponse(BaseSchema):
    """Schema for contact list item (minimal info)."""

    conv_id: str = Field(..., description="Conversation identifier")
    contact_qiao_id: str = Field(..., description="Contact external ID")
    contact_type: ContactType = Field(..., description="Contact type")
    alias: Optional[str] = Field(None, description="Contact alias/remark name")
    avatar_alias_url: Optional[str] = Field(None, description="Custom avatar URL")
    is_pinned: bool = Field(..., description="Is pinned")
    is_muted: bool = Field(..., description="Is muted")
    is_blocked: bool = Field(..., description="Is blocked")
    created_at: datetime = Field(..., description="Contact creation time")


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
    to_type: ContactType = Field(..., description="Target type")
    message: Optional[str] = Field(None, max_length=500, description="Application message")
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


class ContactRequestUpdate(BaseModel):
    """Schema for updating contact request status."""

    status: ContactRequestStatus = Field(..., description="New request status")


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

    contact_qiao_ids: List[str] = Field(..., min_items=1, max_items=50, description="Contact external IDs")
    is_pinned: Optional[bool] = Field(None, description="Pin/unpin contacts")
    is_muted: Optional[bool] = Field(None, description="Mute/unmute contacts")
    is_blocked: Optional[bool] = Field(None, description="Block/unblock contacts")


class BatchContactDelete(BaseModel):
    """Schema for batch deleting contacts."""

    contact_qiao_ids: List[str] = Field(..., min_items=1, max_items=50, description="Contact external IDs")
    permanent: bool = Field(False, description="Permanent deletion (cannot be restored)")
