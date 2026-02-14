"""User management related schemas.

This module contains Pydantic schemas for user accounts, tokens, and authentication.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.enums import AuthType, DeviceType, LoginResult, LoginType, UserStatus, UserType
from app.schemas.common import BaseSchema

# User Schemas


class UserBase(BaseSchema):
    """Base user schema with common fields."""

    username: str = Field(..., min_length=5, max_length=20, description="Username")
    phone: str | None = Field(None, max_length=20, description="Phone number")
    email: str | None = Field(None, max_length=100, description="Email address")
    user_type: UserType = Field(UserType.NORMAL, description="User type")


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    phone: str | None = Field(None, max_length=20, description="Phone number for registration")
    email: str | None = Field(None, max_length=100, description="Email address for registration")
    password: str | None = Field(None, min_length=8, max_length=128, description="Password")
    username: str | None = Field(None, min_length=5, max_length=20, description="Custom username")

    @model_validator(mode="after")
    def validate_login_method(self) -> "UserCreate":
        """Ensure at least one login method is provided."""
        if not self.phone and not self.email:
            raise ValueError("Either phone or email must be provided")
        return self


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    username: str | None = Field(None, min_length=5, max_length=20, description="Username")
    phone: str | None = Field(None, max_length=20, description="Phone number")
    email: str | None = Field(None, max_length=100, description="Email address")


class UserResponse(UserBase):
    """Schema for user response data."""

    qiao_id: str = Field(..., description="External user identifier")
    status: UserStatus = Field(..., description="Account status")
    last_login: datetime | None = Field(None, description="Last login time")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")


class UserListResponse(BaseSchema):
    """Schema for user list item (minimal info)."""

    qiao_id: str = Field(..., description="External user identifier")
    username: str = Field(..., description="Username")
    status: UserStatus = Field(..., description="Account status")
    user_type: UserType = Field(..., description="User type")
    created_at: datetime = Field(..., description="Account creation time")


# Token Schemas


class TokenCreate(BaseModel):
    """Schema for creating a user token."""

    device_type: DeviceType = Field(..., description="Device type")
    device_id: UUID | None = Field(None, description="Device identifier (UUID)")
    platform_info: dict[str, Any] | None = Field(None, description="Platform information")
    ip_address: str | None = Field(None, max_length=45, description="IP address")
    user_agent: str | None = Field(None, description="User agent string")


class TokenUpdate(BaseModel):
    """Schema for updating a user token."""

    device_type: DeviceType | None = Field(None, description="Device type")
    device_id: UUID | None = Field(None, description="Device identifier (UUID)")
    platform_info: dict[str, Any] | None = Field(None, description="Platform information")
    ip_address: str | None = Field(None, max_length=45, description="IP address")
    user_agent: str | None = Field(None, description="User agent string")
    access_expires_at: datetime | None = Field(None, description="Access token expiration time")
    status: int | None = Field(None, description="Token status: 1=active, 2=revoked")
    last_activity_at: datetime | None = Field(None, description="Last activity time")
    access_revoked_at: datetime | None = Field(None, description="Access token revocation time")
    refresh_expires_at: datetime | None = Field(None, description="Refresh token expiration time")
    refresh_revoked_at: datetime | None = Field(None, description="Refresh token revocation time")


class TokenResponse(BaseSchema):
    """Schema for token response data."""

    access_token: str = Field(..., description="Access token (JWT)")
    device_type: DeviceType = Field(..., description="Device type")
    device_id: UUID | None = Field(None, description="Device identifier (UUID)")
    access_expires_at: datetime = Field(..., description="Access token expiration time")
    status: int = Field(..., description="Token status: 1=active, 2=revoked")
    last_activity_at: datetime = Field(..., description="Last activity time")
    access_revoked_at: datetime | None = Field(None, description="Access token revocation time")
    refresh_expires_at: datetime | None = Field(None, description="Refresh token expiration time")
    refresh_revoked_at: datetime | None = Field(None, description="Refresh token revocation time")
    created_at: datetime = Field(..., description="Token creation time")


# Authentication Schemas


class LoginRequest(BaseModel):
    """Schema for login request."""

    phone: str | None = Field(None, max_length=20, description="Phone number")
    email: str | None = Field(None, max_length=100, description="Email address")
    password: str | None = Field(None, min_length=1, description="Password")
    sms_code: str | None = Field(
        None, min_length=4, max_length=10, description="SMS verification code"
    )
    login_type: LoginType = Field(..., description="Login method")
    device_type: DeviceType = Field(..., description="Device type")
    device_id: UUID | None = Field(None, description="Device identifier (UUID)")

    @model_validator(mode="after")
    def validate_login_identifier(self) -> "LoginRequest":
        """Validate login identifier based on login type."""
        if self.login_type == LoginType.SMS and not self.phone:
            raise ValueError("Phone number is required for SMS login")
        if self.login_type == LoginType.PASSWORD and not (self.phone or self.email):
            raise ValueError("Phone or email is required for password login")
        return self


class LoginResponse(BaseSchema):
    """Schema for login response."""

    user: UserResponse = Field(..., description="User information")
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class LogoutRequest(BaseModel):
    """Schema for logout request."""

    token: str = Field(..., description="JWT token to revoke")


# Password Management Schemas


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ResetPasswordRequest(BaseModel):
    """Schema for password reset request."""

    phone: str | None = Field(None, max_length=20, description="Phone number")
    email: str | None = Field(None, max_length=100, description="Email address")

    @model_validator(mode="after")
    def validate_reset_identifier(self) -> "ResetPasswordRequest":
        """Ensure at least one identifier is provided."""
        if not self.phone and not self.email:
            raise ValueError("Either phone or email must be provided")
        return self


class ConfirmResetPasswordRequest(BaseModel):
    """Schema for confirming password reset."""

    phone: str | None = Field(None, max_length=20, description="Phone number")
    email: str | None = Field(None, max_length=100, description="Email address")
    verification_code: str = Field(
        ..., min_length=4, max_length=10, description="Verification code"
    )
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


# Third-Party Authentication Schemas


class UserAuthCreate(BaseModel):
    """Schema for creating a user auth binding."""

    user_id: int = Field(..., description="User internal ID")
    user_qiao_id: str = Field(..., max_length=32, description="User external ID")
    auth_type: AuthType = Field(..., description="Auth provider type")
    provider_uid: str = Field(..., max_length=128, description="Provider user unique ID")
    unionid: str | None = Field(None, max_length=64, description="WeChat unionid")
    app_id: str | None = Field(None, max_length=64, description="Provider app ID")
    extra_data: dict[str, Any] | None = Field(None, description="Extra provider data")
    status: int | None = Field(1, description="Binding status: 1=active, 2=revoked")
    revoked_at: datetime | None = Field(None, description="Unbind time")


class UserAuthUpdate(BaseModel):
    """Schema for updating a user auth binding."""

    unionid: str | None = Field(None, max_length=64, description="WeChat unionid")
    app_id: str | None = Field(None, max_length=64, description="Provider app ID")
    extra_data: dict[str, Any] | None = Field(None, description="Extra provider data")
    status: int | None = Field(None, description="Binding status: 1=active, 2=revoked")
    revoked_at: datetime | None = Field(None, description="Unbind time")


# Login Record Schemas


class LoginRecordCreate(BaseModel):
    """Schema for creating a login record."""

    user_id: int | None = Field(None, description="User internal ID")
    user_qiao_id: str | None = Field(None, max_length=32, description="User external ID")
    login_time: datetime | None = Field(None, description="Login attempt time")
    login_type: LoginType = Field(..., description="Login method")
    platform: DeviceType = Field(..., description="Platform used for login")
    device_id: UUID | None = Field(None, description="Device identifier (UUID)")
    ip_address: str | None = Field(None, max_length=45, description="Login IP address")
    user_agent: str | None = Field(None, description="User agent string")
    result: LoginResult = Field(..., description="Login result")
    fail_reason: str | None = Field(None, max_length=255, description="Failure reason")
    user_token_id: int | None = Field(None, description="Associated user_tokens.id on success")
