"""
Simplified admin user schemas.
Uses role field instead of complex role relationships.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class BaseUser(BaseModel):
    """Base user schema for responses"""

    id: int
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    real_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = "admin"
    is_active: Optional[bool] = True
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    login_count: Optional[int] = 0
    position: Optional[str] = None
    notes: Optional[str] = None


class UserCreate(BaseModel):
    """Schema for creating new admin user"""

    email: EmailStr = Field(example="admin@example.com")
    username: str = Field(example="admin")
    password: str = Field(example="admin123")
    real_name: Optional[str] = Field(None, example="Administrator")
    phone: Optional[str] = Field(None, example="13800138000")
    role: Optional[str] = Field("admin", example="admin", description="Role: super_admin, admin, viewer")
    is_active: Optional[bool] = True
    position: Optional[str] = Field(None, example="System Administrator")
    notes: Optional[str] = Field(None, example="Additional notes")

    def create_dict(self):
        """Convert to dict for database creation"""
        return self.model_dump(exclude_unset=True, exclude={"password"})


class UserUpdate(BaseModel):
    """Schema for updating admin user"""

    id: int
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    real_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = Field(None, description="Role: super_admin, admin, viewer")
    is_active: Optional[bool] = None
    position: Optional[str] = None
    notes: Optional[str] = None

    def update_dict(self):
        """Convert to dict for database update"""
        return self.model_dump(exclude_unset=True, exclude={"id", "password"})


class UpdatePassword(BaseModel):
    """Schema for password update"""

    old_password: str = Field(description="Current password")
    new_password: str = Field(description="New password")
