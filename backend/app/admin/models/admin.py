"""
Simplified admin models.
Contains only essential admin user model with role-based permissions.
"""

import enum
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Enum

from .base import AdminBaseModel, TimestampMixin


class AdminRole(enum.Enum):
    """Admin role enumeration"""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    VIEWER = "viewer"


class AdminUser(AdminBaseModel, TimestampMixin):
    """
    Simplified admin user model.
    Uses role field instead of complex role relationships.
    """

    __tablename__ = "admin_users"

    username = Column(String(50), unique=True, nullable=False, index=True, comment="Admin username")
    email = Column(String(100), unique=True, nullable=True, index=True, comment="Email address")
    password_hash = Column(String(255), nullable=False, comment="Password hash")
    real_name = Column(String(50), nullable=True, comment="Real name")
    phone = Column(String(20), nullable=True, index=True, comment="Phone number")
    # Role field - must be explicitly specified, no default value
    role = Column(
        Enum("super_admin", "admin", "viewer", name="admin_role_enum"),
        nullable=False,
        index=True,
        comment="Admin role: super_admin=Super Admin, admin=Admin, viewer=Viewer",
    )
    is_active = Column(Boolean, default=True, index=True, comment="Account active status")
    last_login = Column(DateTime, nullable=True, index=True, comment="Last login time")
    login_count = Column(Integer, default=0, comment="Login count")
    avatar_url = Column(String(500), nullable=True, comment="Avatar URL")
    position = Column(String(100), nullable=True, comment="Position/Title")
    notes = Column(Text, nullable=True, comment="Additional notes")
    created_by = Column(Integer, nullable=True, comment="Creator user ID")

    def has_permission(self, permission: str) -> bool:
        """
        Check if admin user has specific permission.

        Args:
            permission: Permission to check (e.g., 'create_user', 'delete_bot')

        Returns:
            bool: True if user has permission
        """
        if not self.is_active:
            return False

        if self.role == AdminRole.SUPER_ADMIN.value:
            return True

        # Define permissions for each role
        role_permissions = {
            AdminRole.ADMIN.value: [
                "view_users",
                "create_user",
                "update_user",
                "disable_user",
                "view_bots",
                "create_bot",
                "update_bot",
                "delete_bot",
                "view_contacts",
                "delete_contact",
                "view_messages",
                "view_logs",
            ],
            AdminRole.VIEWER.value: [
                "view_users",
                "view_bots",
                "view_contacts",
                "view_messages",
                "view_logs",
            ],
        }

        # Ensure role exists in permissions mapping
        if self.role not in role_permissions:
            raise ValueError(f"Unknown admin role: {self.role}")

        return permission in role_permissions[self.role]

    def is_super_admin(self) -> bool:
        """Check if user is super admin."""
        return self.is_active and self.role == AdminRole.SUPER_ADMIN.value

    def can_manage_users(self) -> bool:
        """Check if user can manage other admin users."""
        return self.is_super_admin()

    @property
    def role_display(self) -> str:
        """Get display name for role."""
        role_names = {
            AdminRole.SUPER_ADMIN.value: "Super Admin",
            AdminRole.ADMIN.value: "Admin",
            AdminRole.VIEWER.value: "Viewer",
        }
        if self.role not in role_names:
            raise ValueError(f"Unknown admin role: {self.role}")
        return role_names[self.role]
