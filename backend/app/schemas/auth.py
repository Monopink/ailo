"""
Authentication schemas
"""

from pydantic import BaseModel, Field
from typing import Optional


class WeChatLoginRequest(BaseModel):
    """WeChat login request"""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str = Field(..., description="Phone code from getPhoneNumber button")


class WeChatLoginResponse(BaseModel):
    """WeChat login response"""

    success: bool = Field(..., description="Login success")
    needs_phone_binding: bool = Field(default=False, description="Whether user needs to bind phone via SMS")
    wechat_code: Optional[str] = Field(None, description="Temporary code for phone binding")
    user: Optional[dict] = Field(None, description="User info if login successful")
    message: Optional[str] = Field(None, description="Error or info message")


class BindPhoneRequest(BaseModel):
    """Bind phone request"""

    wechat_code: str = Field(..., description="Temporary code from WeChat login")
    phone: str = Field(..., description="Phone number in E.164 format")
    sms_code: str = Field(..., description="SMS verification code")


class BindPhoneResponse(BaseModel):
    """Bind phone response"""

    success: bool = Field(..., description="Bind success")
    user: Optional[dict] = Field(None, description="User info if bind successful")
    message: Optional[str] = Field(None, description="Error or info message")
