"""Authentication schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.enums import DeviceType
from app.type_defs import JSONDict


class WeChatLoginRequest(BaseModel):
    """WeChat login check request (openid + device)."""

    login_code: str = Field(..., description="Login code from wx.login()")
    device_id: UUID = Field(..., description="Device/installation UUID")


class WeChatLoginResponse(BaseModel):
    """WeChat login check response (two-stage)."""

    status: Literal["bound", "need_phone"] = Field(..., description="Login stage result")
    access_token: str | None = Field(
        None, description="Access token when status=bound, otherwise null"
    )
    refresh_token: str | None = Field(
        None, description="Refresh token when status=bound, otherwise null"
    )
    expires_in: int | None = Field(
        None, description="Access token lifetime in seconds when status=bound"
    )
    needs_profile_setup: bool | None = Field(
        None, description="Whether the logged-in user must complete profile setup (bound only)"
    )
    user: JSONDict | None = Field(None, description="User info when status=bound")
    message: str | None = Field(None, description="Info message")


class WeChatBindPhoneRequest(BaseModel):
    """WeChat bind phone request (second stage)."""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str | None = Field(
        None, description="Phone code from getPhoneNumber button (new protocol)"
    )
    encrypted_data: str | None = Field(
        None, description="Encrypted phone payload from getPhoneNumber (legacy protocol)"
    )
    iv: str | None = Field(
        None, description="IV for encrypted phone payload from getPhoneNumber (legacy protocol)"
    )
    device_id: UUID = Field(..., description="Device/installation UUID")

    @model_validator(mode="after")
    def validate_phone_payload(self) -> "WeChatBindPhoneRequest":
        """Ensure bind request contains exactly one valid phone payload format."""
        has_phone_code = bool(self.phone_code and self.phone_code.strip())
        has_encrypted_data = bool(self.encrypted_data and self.encrypted_data.strip())
        has_iv = bool(self.iv and self.iv.strip())

        if has_phone_code:
            return self
        if has_encrypted_data and has_iv:
            return self
        raise ValueError("phone_code or encrypted_data+iv is required")


class WeChatBindPhoneResponse(BaseModel):
    """WeChat bind phone response."""

    status: Literal["success"] = Field(..., description="Binding result status")
    access_token: str = Field(..., description="Access token after binding")
    refresh_token: str = Field(..., description="Refresh token after binding")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    needs_profile_setup: bool = Field(..., description="Whether profile setup is required")
    user: JSONDict = Field(..., description="User info after binding")
    message: str | None = Field(None, description="Optional message for binding update")
    binding_reused: bool | None = Field(
        None, description="Whether an existing account was reused and old binding replaced"
    )
    replaced_old_wechat: bool | None = Field(
        None, description="Whether an old WeChat binding was replaced"
    )


class WeChatRefreshPhoneRequest(BaseModel):
    """WeChat phone refresh request."""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str = Field(..., description="Phone code from getPhoneNumber button")


class WeChatRefreshPhoneResponse(BaseModel):
    """WeChat phone refresh response."""

    phone: str = Field(..., description="Masked phone number")
    user: JSONDict = Field(..., description="Updated user info payload")


class VerifyPhoneRequest(BaseModel):
    """Phone verification request (unified login/registration entry)."""

    phone: str = Field(..., description="Phone number in E.164 format")
    sms_code: str = Field(..., description="SMS verification code")
    device_id: UUID = Field(..., description="Device/installation UUID")


class VerifyPhoneResponse(BaseModel):
    """Phone verification response."""

    access_token: str = Field(..., description="Access token for authenticated user")
    refresh_token: str = Field(..., description="Refresh token for authenticated user")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    needs_profile_setup: bool = Field(..., description="Whether profile setup is required")
    user: JSONDict = Field(..., description="User info for the authenticated session")


class RefreshTokenRequest(BaseModel):
    """Access token refresh request."""

    refresh_token: str = Field(..., description="Refresh token issued during login")


class RefreshTokenResponse(BaseModel):
    """Access token refresh response."""

    access_token: str = Field(..., description="New access token")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class PasswordLoginRequest(BaseModel):
    """Password login request."""

    identifier: str = Field(
        ...,
        description="Login identifier: username | phone | email",
        min_length=1,
        max_length=100,
    )
    password: str = Field(..., description="Plain password", min_length=1, max_length=200)
    device_id: UUID = Field(..., description="Device/installation UUID")
    device_type: DeviceType = Field(
        ...,
        description="Device type enum: 1=ios, 2=android, 3=web, 4=mini_program",
    )


class PasswordLoginResponse(BaseModel):
    """Password login response."""

    access_token: str = Field(..., description="Access token for authenticated user")
    refresh_token: str = Field(..., description="Refresh token for authenticated user")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    needs_profile_setup: bool = Field(..., description="Whether profile setup is required")
    user: JSONDict = Field(..., description="User info for the authenticated session")
