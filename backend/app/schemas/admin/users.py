"""
Admin user schemas matching actual database fields.
Only includes fields that exist in the database.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from enums import AdminRole


class BaseUser(BaseModel):
    """Base user schema for responses - matches database fields"""

    id: int
    username: str
    role: int
    is_active: bool = True
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    login_count: int = 0


class UserCreate(BaseModel):
    """Schema for creating new admin user - matches database fields"""

    username: str = Field(example="admin")
    password: str = Field(example="admin123")
    role: int = Field(AdminRole.ADMIN, description="Role: 1=super_admin, 2=admin, 3=viewer")


class UserUpdate(BaseModel):
    """Schema for updating admin user - matches database fields"""

    id: int
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[int] = Field(None, description="Role: 1=super_admin, 2=admin, 3=viewer")


class AdminChangePasswordRequest(BaseModel):
    """Schema for admin password change request"""

    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class AdminOperationLogBase(BaseModel):
    """Base schema for admin operation logs"""

    id: int
    admin_id: int
    operation: str
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminOperationLogCreate(BaseModel):
    """Schema for creating admin operation log"""

    admin_id: int
    operation: str
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AdminOperationLogResponse(AdminOperationLogBase):
    """Schema for admin operation log response"""

    pass


class AdminLoginLogResponse(BaseModel):
    """Schema for admin login log response"""

    id: int
    admin_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    login_time: Optional[datetime] = None
    success: bool = True


class AdminDashboardStats(BaseModel):
    """Schema for admin dashboard statistics"""

    total_users: int = 0
    active_users: int = 0
    total_operations: int = 0
    recent_logins: int = 0


class AdminSystemInfo(BaseModel):
    """Schema for admin system information"""

    version: str
    uptime: str
    memory_usage: str
    cpu_usage: str


class BatchAdminUserUpdate(BaseModel):
    """Schema for batch updating admin users"""

    user_ids: list[int]
    updates: UserUpdate
