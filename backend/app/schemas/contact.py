from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ContactTypeEnum(int, Enum):
    """Contact type enumeration"""

    BOT = 1
    USER = 2


class ContactStatusEnum(str, Enum):
    """Contact status enumeration"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class ContactCreate(BaseModel):
    """Schema for creating a contact relationship"""

    contact_entity_id: str = Field(..., description="Entity ID of the contact to add")
    contact_type: ContactTypeEnum = Field(..., description="Type of contact (bot or user)")


class ContactUpdate(BaseModel):
    """Schema for updating contact information"""

    status: Optional[ContactStatusEnum] = Field(None, description="Contact status")


class ContactResponse(BaseModel):
    """Schema for contact response"""

    id: int = Field(..., description="Contact relationship ID")
    user_entity_id: str = Field(..., description="User's entity ID")
    contact_entity_id: str = Field(..., description="Contact's entity ID")
    contact_type: ContactTypeEnum = Field(..., description="Type of contact")
    status: ContactStatusEnum = Field(..., description="Contact status")
    added_at: datetime = Field(..., description="When the contact was added")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Schema for contact list response with profile information"""

    id: str = Field(..., description="Contact entity ID (mapped for frontend)")
    nickname: Optional[str] = Field(None, description="Contact nickname")
    avatar_url: Optional[str] = Field(None, description="Contact avatar URL")
    contact_type: ContactTypeEnum = Field(..., description="Type of contact")
    status: ContactStatusEnum = Field(..., description="Contact status")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")

    class Config:
        from_attributes = True


class ContactLimitsResponse(BaseModel):
    """Schema for contact limits information"""

    current_count: int = Field(..., description="Current number of contacts")
    limit: int = Field(..., description="Maximum allowed contacts")
    remaining: int = Field(..., description="Remaining contact slots")
    can_add_more: bool = Field(..., description="Whether user can add more contacts")

    class Config:
        from_attributes = True


class ContactSearchResponse(BaseModel):
    """Schema for contact search results"""

    id: str = Field(..., description="Contact entity ID")
    nickname: str = Field(..., description="Contact nickname")
    avatar_url: Optional[str] = Field(None, description="Contact avatar URL")
    bio: Optional[str] = Field(None, description="Contact bio")
    contact_type: ContactTypeEnum = Field(..., description="Type of contact")
    is_available: bool = Field(..., description="Whether contact can be added")

    class Config:
        from_attributes = True
