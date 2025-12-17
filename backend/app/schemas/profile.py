"""
Profile schemas for request/response validation
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileBase(BaseModel):
    """Base profile schema matching Profile model"""

    nickname: str | None = Field(None, max_length=10, description="Display nickname")
    gender: int | None = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_file_id: int | None = Field(None, description="Foreign key to media_files.id")
    avatar_prompt: str | None = Field(
        None, description="Avatar description for LLM prompt replacement"
    )
    bio: str | None = Field(None, max_length=70, description="Personal bio/description")
    region: str | None = Field(None, max_length=100, description="Location/region")


class ProfileCreate(ProfileBase):
    """Schema for creating a profile"""


class ProfileUpdate(ProfileBase):
    """Schema for updating a profile"""


class ProfileInDBBase(ProfileBase):
    """Base schema for profile in database"""

    id: int
    owner_id: int
    owner_qiao_id: str
    owner_type: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Profile(ProfileInDBBase):
    """Schema for profile response"""


class ProfileInDB(ProfileInDBBase):
    """Schema for profile in database (internal use)"""
