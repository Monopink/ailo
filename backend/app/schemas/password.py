"""
Password management schemas
"""

from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    """Request schema for changing password"""

    old_password: str | None = Field(None, description="Current password, optional for first-time setup")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password (8-128 characters)"
    )


class ResetPasswordRequest(BaseModel):
    """Request schema for resetting password"""

    operation_token: str = Field(..., description="Operation token from verification")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password (8-128 characters)"
    )
