"""
Verification schemas for unified verification mechanism
"""

from typing import Literal

from pydantic import BaseModel, Field


class VerifySendCodeRequest(BaseModel):
    """Request schema for sending verification code"""

    verify_type: Literal["phone", "email"] = Field(..., description="Verification type: phone or email")
    target: str | None = Field(None, description="Target phone/email, defaults to current user's")
    # For phone verification flows, CAPTCHA is required on each send
    captcha_token: str | None = Field(None, description="CAPTCHA verification token (Turnstile)")


class VerifySendCodeResponse(BaseModel):
    """Response schema for sending verification code"""

    cooldown: int = Field(..., description="Cooldown time in seconds before next code can be sent")


class VerifyConfirmRequest(BaseModel):
    """Request schema for confirming verification code"""

    verify_type: Literal["phone", "email"] = Field(..., description="Verification type: phone or email")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class OperationTokenResponse(BaseModel):
    """Response schema for operation token"""

    operation_token: str = Field(..., description="Operation token for sensitive operations")
    expires_in: int = Field(..., description="Token expiration time in seconds")
