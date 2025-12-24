"""
Authentication schemas
"""

from typing import Any

from pydantic import BaseModel, Field


class WeChatLoginRequest(BaseModel):
    """WeChat login request"""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str = Field(..., description="Phone code from getPhoneNumber button")


class WeChatLoginResponse(BaseModel):
    """WeChat login response"""

    success: bool = Field(True, description="Login success")
    token: str = Field(..., description="JWT token when login succeeds")
    needs_profile_setup: bool = Field(
        ..., description="Whether the logged-in user must complete profile setup"
    )
    user: dict[str, Any] = Field(..., description="User info if login successful")
    message: str | None = Field(None, description="Error or info message")


class WeChatRefreshPhoneRequest(BaseModel):
    """WeChat phone refresh request"""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str = Field(..., description="Phone code from getPhoneNumber button")


class WeChatRefreshPhoneResponse(BaseModel):
    """WeChat phone refresh response"""

    phone: str = Field(..., description="Masked phone number")
    user: dict[str, Any] = Field(..., description="Updated user info payload")


class VerifyPhoneRequest(BaseModel):
    """Phone verification request (unified login/registration entry)"""

    phone: str = Field(..., description="Phone number in E.164 format")
    sms_code: str = Field(..., description="SMS verification code")


class VerifyPhoneResponse(BaseModel):
    """Phone verification response"""

    token: str = Field(..., description="JWT token for authenticated user")
    needs_profile_setup: bool = Field(..., description="Whether profile setup is required")
    user: dict[str, Any] = Field(..., description="User info for the authenticated session")
