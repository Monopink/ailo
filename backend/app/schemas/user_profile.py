"""User profile schemas for API request/response."""

import re

from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """User profile response schema for GET /api/v1/user/profile - only profile data."""

    qiao_id: str = Field(..., description="User external ID")
    username: str | None = Field(None, description="User-customizable ID, NULL if not set")
    nickname: str | None = Field(None, description="Display nickname")
    gender: int | None = Field(None, description="Gender: 1=male, 2=female, 3=other; null=unknown")
    avatar_url: str | None = Field(None, description="Dynamically generated avatar CDN URL")
    bio: str | None = Field(None, description="Personal bio/description")
    region: str | None = Field(None, description="Location/region")


class UserAccountResponse(BaseModel):
    """User account response schema for GET /api/v1/user/account - security info."""

    qiao_id: str = Field(..., description="User external ID")
    username: str | None = Field(None, description="Username for login, NULL if not set")
    phone: str = Field(..., description="Masked phone number (138******00)")
    email: str | None = Field(
        None, description="Masked email (u***@example.com), null if not bound"
    )
    has_password: bool = Field(..., description="Whether user has set password")


class UserProfileUpdateRequest(BaseModel):
    """User profile update request schema for PUT /api/v1/user/profile."""

    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(None, description="Username, user can only set once")
    nickname: str | None = Field(None, max_length=32, description="Display nickname")
    gender: int | None = Field(
        None, ge=1, le=3, description="Gender: 1=male, 2=female, 3=other; null=unknown"
    )
    avatar_file_id: str | None = Field(
        None,
        description=("File ID (file_xxx format) - converted to avatar_key and avatar_media_id."),
    )
    bio: str | None = Field(None, max_length=120, description="Personal bio/description")
    region_country_code: str | None = Field(
        None,
        max_length=2,
        description="Region country/territory code",
    )
    region_cn_city_code: str | None = Field(
        None, max_length=6, description="CN city-level administrative division code (6 digits)"
    )
    region_province_name: str | None = Field(
        None,
        max_length=50,
        description="CN province-level name selected by client",
    )
    region_city_name: str | None = Field(
        None,
        max_length=50,
        description="CN city-level name selected by client",
    )

    @staticmethod
    def is_valid_cn_city_code(value: str) -> bool:
        """Return True if value is a 6-digit CN city code."""
        return bool(re.fullmatch(r"\d{6}", value))


class UsernameCheckResponse(BaseModel):
    """Username availability check response schema."""

    available: bool = Field(..., description="Whether username can be used now")
