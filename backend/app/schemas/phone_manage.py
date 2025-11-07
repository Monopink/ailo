"""
Phone number management schemas
"""

from typing import Optional

from pydantic import BaseModel, Field


class ChangePhoneRequest(BaseModel):
    """Request schema for changing phone number"""

    operation_token: Optional[str] = Field(None, description="Operation token from verification")
    new_phone: str = Field(..., max_length=20, description="New phone number in E.164 format")
    sms_code: str = Field(
        ..., min_length=6, max_length=6, description="6-digit SMS verification code for new phone"
    )


class ChangePhoneResponse(BaseModel):
    """Response schema for changing phone number"""

    phone: str = Field(..., description="Masked new phone number")
