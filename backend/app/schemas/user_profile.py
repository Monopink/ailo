"""
User profile schemas for API request/response
"""

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """User profile response schema for GET /api/v1/user/profile - only profile data"""

    qiao_id: str = Field(..., description="User external ID")
    username: str = Field(..., description="User-customizable ID")
    nickname: str | None = Field(None, description="Display nickname")
    gender: int | None = Field(None, description="Gender: 1=male, 2=female, 3=other, 4=unknown")
    avatar_url: str | None = Field(None, description="Dynamically generated avatar CDN URL")
    bio: str | None = Field(None, description="Personal bio/description")
    region: str | None = Field(None, description="Location/region")


class UserAccountResponse(BaseModel):
    """User account response schema for GET /api/v1/user/account - security info"""

    qiao_id: str = Field(..., description="User external ID")
    username: str = Field(..., description="Username for login")
    phone: str = Field(..., description="Masked phone number (138******00)")
    email: str | None = Field(
        None, description="Masked email (u***@example.com), null if not bound"
    )
    has_password: bool = Field(..., description="Whether user has set password")


class UserProfileUpdateRequest(BaseModel):
    """User profile update request schema for PUT /api/v1/user/profile"""

    username: str | None = Field(
        None, min_length=3, max_length=20, description="User-customizable ID"
    )
    nickname: str | None = Field(None, max_length=10, description="Display nickname")
    gender: int | None = Field(
        None, ge=1, le=4, description="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )
    avatar_file_id: str | None = Field(
        None,
        description=("File ID (file_xxx format) - converted to avatar_key and avatar_media_id."),
    )
    bio: str | None = Field(None, max_length=70, description="Personal bio/description")
    region: str | None = Field(None, max_length=100, description="Location/region")
