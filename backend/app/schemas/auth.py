"""
Authentication schemas
"""

from pydantic import BaseModel, Field


class WeChatLoginRequest(BaseModel):
    """WeChat login request"""

    login_code: str = Field(..., description="Login code from wx.login()")
    phone_code: str = Field(..., description="Phone code from getPhoneNumber button")


class WeChatLoginResponse(BaseModel):
    """WeChat login response"""

    success: bool = Field(..., description="Login success")
    needs_phone_binding: bool = Field(
        default=False, description="Whether user needs to bind phone via SMS"
    )
    wechat_code: str | None = Field(None, description="Temporary code for phone binding")
    user: dict | None = Field(None, description="User info if login successful")
    message: str | None = Field(None, description="Error or info message")


class BindPhoneRequest(BaseModel):
    """Bind phone request"""

    wechat_code: str = Field(..., description="Temporary code from WeChat login")
    phone: str = Field(..., description="Phone number in E.164 format")
    sms_code: str = Field(..., description="SMS verification code")


class BindPhoneResponse(BaseModel):
    """Bind phone response"""

    success: bool = Field(..., description="Bind success")
    user: dict | None = Field(None, description="User info if bind successful")
    message: str | None = Field(None, description="Error or info message")


class VerifyPhoneRequest(BaseModel):
    """Phone verification request (unified login/registration entry)"""

    phone: str = Field(..., description="Phone number in E.164 format")
    sms_code: str = Field(..., description="SMS verification code")
    wechat_code: str | None = Field(None, description="Optional WeChat code for binding")


class VerifyPhoneResponse(BaseModel):
    """Phone verification response"""

    is_new_user: bool = Field(..., description="Whether user is new (needs profile setup)")
    token: str | None = Field(None, description="JWT token if user exists")
    user: dict | None = Field(None, description="User info if user exists")
    verified_phone_token: str | None = Field(
        None, description="Temporary token for new user registration"
    )
    phone: str | None = Field(None, description="Phone number for new user")


class CompleteRegistrationRequest(BaseModel):
    """Complete registration request"""

    verified_phone_token: str = Field(..., description="Temporary token from phone verification")
    nickname: str = Field(
        ..., min_length=2, max_length=20, description="User nickname (2-20 characters)"
    )
    gender: int | None = Field(None, description="Gender: 0=unknown, 1=male, 2=female")
    bio: str | None = Field(None, max_length=200, description="User bio (max 200 characters)")
    avatar_url: str | None = Field(None, description="Avatar URL")


class CompleteRegistrationResponse(BaseModel):
    """Complete registration response"""

    token: str = Field(..., description="JWT token")
    user: dict = Field(..., description="User info")
