"""Admin management related schemas.

This module contains Pydantic schemas for admin users and operation logs.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import AdminRole
from app.schemas.common import BaseSchema

# Admin User Schemas


class AdminUserBase(BaseSchema):
    """Base admin user schema."""

    username: str = Field(..., min_length=3, max_length=50, description="Admin username")
    role: AdminRole = Field(..., description="Admin role")


class AdminUserCreate(BaseModel):
    """Schema for creating an admin user."""

    username: str = Field(..., min_length=3, max_length=50, description="Admin username")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    role: AdminRole = Field(AdminRole.ADMIN, description="Admin role")


class AdminUserUpdate(BaseModel):
    """Schema for updating admin user."""

    password: str | None = Field(None, min_length=8, max_length=128, description="New password")
    role: AdminRole | None = Field(None, description="Admin role")
    status: int | None = Field(None, description="Account status")


class AdminUserResponse(AdminUserBase):
    """Schema for admin user response data."""

    status: int = Field(..., description="Account status")
    last_login: datetime | None = Field(None, description="Last login time")
    login_count: int = Field(..., description="Login count")
    created_by: int | None = Field(None, description="Creator admin user ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AdminUserListResponse(BaseSchema):
    """Schema for admin user list item."""

    username: str = Field(..., description="Admin username")
    role: AdminRole = Field(..., description="Admin role")
    status: int = Field(..., description="Account status")
    last_login: datetime | None = Field(None, description="Last login time")
    login_count: int = Field(..., description="Login count")
    created_at: datetime = Field(..., description="Creation time")


# Admin Authentication Schemas


class AdminLoginRequest(BaseModel):
    """Schema for admin login request."""

    username: str = Field(..., min_length=1, max_length=50, description="Admin username")
    password: str = Field(..., min_length=1, description="Password")


class AdminLoginResponse(BaseSchema):
    """Schema for admin login response."""

    admin: AdminUserResponse = Field(..., description="Admin user information")
    access_token: str = Field(..., description="Access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class AdminChangePasswordRequest(BaseModel):
    """Schema for admin password change."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")


# Admin Operation Log Schemas


class AdminOperationLogBase(BaseSchema):
    """Base admin operation log schema."""

    operation_type: int = Field(..., description="Operation type")
    resource_type: str = Field(..., max_length=50, description="Resource type")
    resource_id: str | None = Field(None, max_length=100, description="Resource ID")
    resource_name: str | None = Field(None, max_length=200, description="Resource name")
    operation_desc: str = Field(..., max_length=500, description="Operation description")


class AdminOperationLogCreate(BaseModel):
    """Schema for creating admin operation log."""

    admin_user_id: int = Field(..., description="Admin user ID")
    operation_type: int = Field(..., description="Operation type")
    resource_type: str = Field(..., max_length=50, description="Resource type")
    resource_id: str | None = Field(None, max_length=100, description="Resource ID")
    resource_name: str | None = Field(None, max_length=200, description="Resource name")
    operation_desc: str = Field(..., max_length=500, description="Operation description")
    ip_address: str | None = Field(None, max_length=45, description="IP address")
    user_agent: str | None = Field(None, max_length=500, description="User agent")


class AdminOperationLogResponse(AdminOperationLogBase):
    """Schema for admin operation log response data."""

    admin_user_id: int = Field(..., description="Admin user ID")
    ip_address: str | None = Field(None, description="IP address")
    user_agent: str | None = Field(None, description="User agent")
    created_at: datetime = Field(..., description="Operation time")


# Admin Login Log Schemas


class AdminLoginLogResponse(BaseSchema):
    """Schema for admin login log response data."""

    admin_user_id: int | None = Field(None, description="Admin user ID")
    username: str = Field(..., description="Login username")
    user_agent: str | None = Field(None, description="User agent")
    ip_address: str | None = Field(None, description="IP address")
    result: int = Field(..., description="Login result")
    fail_reason: str | None = Field(None, description="Failure reason")
    created_at: datetime = Field(..., description="Login time")


# Admin Dashboard Schemas


class AdminDashboardStats(BaseSchema):
    """Schema for admin dashboard statistics."""

    total_users: int = Field(..., description="Total user count")
    active_users: int = Field(..., description="Active user count")
    total_messages: int = Field(..., description="Total message count")
    total_ai_instances: int = Field(..., description="Total AI instance count")
    daily_new_users: int = Field(..., description="Daily new user count")
    daily_messages: int = Field(..., description="Daily message count")


class AdminSystemInfo(BaseSchema):
    """Schema for admin system information."""

    version: str = Field(..., description="System version")
    uptime: str = Field(..., description="System uptime")
    database_status: str = Field(..., description="Database status")
    total_storage: str = Field(..., description="Total storage usage")


# Batch Admin Operations


class BatchAdminUserUpdate(BaseModel):
    """Schema for batch updating admin users."""

    admin_user_ids: list[int] = Field(
        ..., min_length=1, max_length=50, description="Admin user IDs"
    )
    status: int | None = Field(None, description="New status")
    role: AdminRole | None = Field(None, description="New role")
