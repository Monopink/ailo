"""
Email management schemas
"""

from pydantic import BaseModel, Field


class EmailSendCodeRequest(BaseModel):
    """Request schema for sending email verification code"""

    email: str = Field(..., max_length=100, description="Email address")


class EmailSendCodeResponse(BaseModel):
    """Response schema for sending email verification code"""

    cooldown: int = Field(..., description="Cooldown time in seconds before next code can be sent")


class BindEmailRequest(BaseModel):
    """Request schema for binding email"""

    email: str = Field(..., max_length=100, description="Email address to bind")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class BindEmailResponse(BaseModel):
    """Response schema for binding email"""

    email: str = Field(..., description="Masked email address")


class ChangeEmailRequest(BaseModel):
    """Request schema for changing email"""

    operation_token: str = Field(..., description="Operation token from verification")
    new_email: str = Field(..., max_length=100, description="New email address")
    email_code: str = Field(
        ..., min_length=6, max_length=6, description="6-digit verification code for new email"
    )


class ChangeEmailResponse(BaseModel):
    """Response schema for changing email"""

    email: str = Field(..., description="Masked new email address")


class UnbindEmailRequest(BaseModel):
    """Request schema for unbinding email"""

    operation_token: str = Field(..., description="Operation token from verification")
