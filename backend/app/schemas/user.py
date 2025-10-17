"""
User management related schemas.

This module contains Pydantic schemas for user accounts, sessions, and authentication.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

from enums import UserStatus, UserType, DeviceType, LoginType
from schemas.common import BaseSchema


# User Schemas


class UserBase(BaseSchema):
    """Base user schema with common fields."""

    username: str = Field(..., min_length=1, max_length=50, description="Username")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    user_type: UserType = Field(UserType.NORMAL, description="User type")


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    phone: Optional[str] = Field(None, max_length=20, description="Phone number for registration")
    email: Optional[str] = Field(None, max_length=100, description="Email address for registration")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Password")
    username: Optional[str] = Field(None, min_length=1, max_length=50, description="Custom username")

    @validator("phone", "email")
    def validate_login_method(cls, v, values):
        """Ensure at least one login method is provided."""
        if not v and not values.get("phone") and not values.get("email"):
            raise ValueError("Either phone or email must be provided")
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    username: Optional[str] = Field(None, min_length=1, max_length=50, description="Username")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")


class UserResponse(UserBase):
    """Schema for user response data."""

    qiao_id: str = Field(..., description="External user identifier")
    status: UserStatus = Field(..., description="Account status")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")


class UserListResponse(BaseSchema):
    """Schema for user list item (minimal info)."""

    qiao_id: str = Field(..., description="External user identifier")
    username: str = Field(..., description="Username")
    status: UserStatus = Field(..., description="Account status")
    user_type: UserType = Field(..., description="User type")
    created_at: datetime = Field(..., description="Account creation time")


# Session Schemas


class SessionCreate(BaseModel):
    """Schema for creating a user session."""

    device_type: DeviceType = Field(..., description="Device type")
    device_id: Optional[str] = Field(None, max_length=128, description="Device identifier")
    platform_info: Optional[dict] = Field(None, description="Platform information")
    ip_address: Optional[str] = Field(None, max_length=45, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")


class SessionResponse(BaseSchema):
    """Schema for session response data."""

    session_token: str = Field(..., description="Session token")
    device_type: DeviceType = Field(..., description="Device type")
    device_id: Optional[str] = Field(None, description="Device identifier")
    expires_at: datetime = Field(..., description="Session expiration time")
    status: int = Field(..., description="Session status: 1=active, 2=inactive")
    last_activity_at: datetime = Field(..., description="Last activity time")
    created_at: datetime = Field(..., description="Session creation time")


# Authentication Schemas


class LoginRequest(BaseModel):
    """Schema for login request."""

    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    password: Optional[str] = Field(None, min_length=1, description="Password")
    sms_code: Optional[str] = Field(None, min_length=4, max_length=10, description="SMS verification code")
    login_type: LoginType = Field(..., description="Login method")
    device_type: DeviceType = Field(..., description="Device type")
    device_id: Optional[str] = Field(None, max_length=128, description="Device identifier")

    @validator("phone", "email")
    def validate_login_identifier(cls, v, values):
        """Validate login identifier based on login type."""
        login_type = values.get("login_type")
        if login_type == LoginType.SMS and not values.get("phone"):
            raise ValueError("Phone number is required for SMS login")
        if login_type == LoginType.PASSWORD and not (v or values.get("phone") or values.get("email")):
            raise ValueError("Phone or email is required for password login")
        return v


class LoginResponse(BaseSchema):
    """Schema for login response."""

    user: UserResponse = Field(..., description="User information")
    session_token: str = Field(..., description="Session token")
    expires_at: datetime = Field(..., description="Session expiration time")


class LogoutRequest(BaseModel):
    """Schema for logout request."""

    session_token: str = Field(..., description="Session token to invalidate")


# Password Management Schemas


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


class ResetPasswordRequest(BaseModel):
    """Schema for password reset request."""

    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")

    @validator("phone", "email")
    def validate_reset_identifier(cls, v, values):
        """Ensure at least one identifier is provided."""
        if not v and not values.get("phone") and not values.get("email"):
            raise ValueError("Either phone or email must be provided")
        return v


class ConfirmResetPasswordRequest(BaseModel):
    """Schema for confirming password reset."""

    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    verification_code: str = Field(..., min_length=4, max_length=10, description="Verification code")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
