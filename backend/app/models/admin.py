"""
Admin management related models.

This module contains SQLAlchemy models for admin users and operation logs.
"""

from datetime import datetime
from typing import Optional

from enums import AdminOperationType, AdminRole, AdminStatus
from models.base import AutoIncrementModel, ImmutableAutoIncrementModel, StatusMixin
from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class AdminUser(AutoIncrementModel, StatusMixin):
    """
    Admin user model.

    Admin account management.
    """

    __tablename__ = "admin_users"

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="Admin username")

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="Password hash")

    role: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Role: 1=super_admin, 2=admin, 3=viewer",
    )

    last_login: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last login time"
    )

    login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Login count"
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Creator admin user ID"
    )

    def has_permission(self, permission: str) -> bool:
        """
        Check if admin user has specific permission.

        Args:
            permission: Permission to check (e.g., 'create_user', 'delete_bot')

        Returns:
            bool: True if user has permission
        """
        if self.status != AdminStatus.ACTIVE:
            return False

        if self.role == AdminRole.SUPER_ADMIN:
            return True

        # Define permissions for each role
        role_permissions = {
            AdminRole.ADMIN: [
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
            AdminRole.VIEWER: [
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
        return self.status == AdminStatus.ACTIVE and self.role == AdminRole.SUPER_ADMIN

    def can_manage_users(self) -> bool:
        """Check if user can manage other admin users."""
        return self.is_super_admin()

    @property
    def role_display(self) -> str:
        """Get display name for role."""
        role_names = {
            AdminRole.SUPER_ADMIN: "Super Admin",
            AdminRole.ADMIN: "Admin",
            AdminRole.VIEWER: "Viewer",
        }
        if self.role not in role_names:
            raise ValueError(f"Unknown admin role: {self.role}")
        return role_names[self.role]


class AdminOperationLog(ImmutableAutoIncrementModel):
    """
    Admin operation log model.

    Admin operation tracking.
    Immutable log - operations should not be modified after creation.
    """

    __tablename__ = "admin_operation_logs"

    admin_user_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Admin user ID")

    operation_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Operation: 1=CREATE, 2=UPDATE, 3=DELETE, 4=ENABLE, 5=DISABLE"
    )

    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Resource type: user, ai_instance, config, admin, etc."
    )

    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Resource ID")

    resource_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Resource name"
    )

    operation_desc: Mapped[str] = mapped_column(Text, nullable=False, comment="Operation description")

    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True, comment="IP address")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent")

    @property
    def operation_type_display(self) -> str:
        """Get display name for operation type."""
        try:
            return AdminOperationType(self.operation_type).name
        except (ValueError, AttributeError):
            return f"UNKNOWN({self.operation_type})"


class AdminLoginLog(ImmutableAutoIncrementModel):
    """
    Admin login log model.

    Admin login tracking.
    Immutable log - only has created_at, no updated_at.
    """

    __tablename__ = "admin_login_logs"

    # created_at inherited from ImmutableAutoIncrementModel

    admin_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Admin user ID")

    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="Login username")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent")

    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True, comment="IP address")

    result: Mapped[int] = mapped_column(Integer, nullable=False, comment="Result: 1=success, 2=fail")

    fail_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Failure reason")
