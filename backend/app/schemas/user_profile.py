"""
User profile schemas for API request/response
"""

from typing import Optional

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """User profile response schema for GET /api/v1/user/profile - only profile data"""

    qiao_id: str = Field(..., description="User external ID")
    username: str = Field(..., description="User-customizable ID, displayed as '敲敲ID' in UI")
    nickname: Optional[str] = Field(None, description="Display nickname")
    gender: Optional[int] = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    bio: Optional[str] = Field(None, description="Personal bio/description")
    region: Optional[str] = Field(None, description="Location/region")


class UserAccountResponse(BaseModel):
    """User account response schema for GET /api/v1/user/account - security info"""

    qiao_id: str = Field(..., description="User external ID")
    username: str = Field(..., description="Username for login")
    phone: str = Field(..., description="Masked phone number (138******00)")
    email: Optional[str] = Field(None, description="Masked email (u***@example.com), null if not bound")
    has_password: bool = Field(..., description="Whether user has set password")


class UserProfileUpdateRequest(BaseModel):
    """User profile update request schema for PUT /api/v1/user/profile"""

    username: Optional[str] = Field(None, min_length=3, max_length=20, description="User-customizable ID")
    nickname: Optional[str] = Field(None, max_length=10, description="Display nickname")
    gender: Optional[int] = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar URL")
    bio: Optional[str] = Field(None, max_length=70, description="Personal bio/description")
    region: Optional[str] = Field(None, max_length=100, description="Location/region")
