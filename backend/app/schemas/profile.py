"""
Profile schemas for request/response validation
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class ProfileBase(BaseModel):
    """Base profile schema matching Profile model"""

    nickname: Optional[str] = Field(None, max_length=10, description="Display nickname")
    gender: Optional[int] = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar URL")
    avatar_prompt: Optional[str] = Field(None, description="Avatar description for AI-generated avatars")
    bio: Optional[str] = Field(None, max_length=70, description="Personal bio/description")
    region: Optional[str] = Field(None, max_length=100, description="Location/region")


class ProfileCreate(ProfileBase):
    """Schema for creating a profile"""

    pass


class ProfileUpdate(ProfileBase):
    """Schema for updating a profile"""

    pass


class ProfileInDBBase(ProfileBase):
    """Base schema for profile in database"""

    id: int
    owner_id: int
    owner_qiao_id: str
    owner_type: int
    avatar_file_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Profile(ProfileInDBBase):
    """Schema for profile response"""

    pass


class ProfileInDB(ProfileInDBBase):
    """Schema for profile in database (internal use)"""

    pass
