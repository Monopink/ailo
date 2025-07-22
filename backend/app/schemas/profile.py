from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import date
from enum import Enum


class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class SocialProfileCreate(BaseModel):
    """Schema for creating social profile"""

    nickname: str = Field(..., min_length=1, max_length=50, description="Display nickname")
    gender: GenderEnum = Field(..., description="Gender")
    bio: Optional[str] = Field(None, max_length=500, description="Bio/description")
    birth_date: Optional[date] = Field(None, description="Birth date")
    location: Optional[str] = Field(None, max_length=100, description="Location")

    @validator("nickname")
    def validate_nickname(cls, v):
        if not v or not v.strip():
            raise ValueError("Nickname cannot be empty")
        return v.strip()


class SocialProfileUpdate(BaseModel):
    """Schema for updating social profile"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="Display nickname")
    gender: Optional[GenderEnum] = Field(None, description="Gender")
    bio: Optional[str] = Field(None, max_length=500, description="Bio/description")
    birth_date: Optional[date] = Field(None, description="Birth date")
    location: Optional[str] = Field(None, max_length=100, description="Location")

    @validator("nickname")
    def validate_nickname(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError("Nickname cannot be empty")
        return v.strip() if v else v


class SocialProfileResponse(BaseModel):
    """Schema for social profile response"""

    id: str = Field(..., description="Entity ID")
    nickname: Optional[str] = Field(None, description="Display nickname")
    gender: Optional[GenderEnum] = Field(None, description="Gender")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Bio/description")
    birth_date: Optional[date] = Field(None, description="Birth date")
    location: Optional[str] = Field(None, description="Location")

    class Config:
        from_attributes = True
