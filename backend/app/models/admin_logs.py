"""
Admin log models for operation and login tracking.
Simplified logging system for admin activities.
"""

from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship

from .base import ImmutableAutoIncrementModel


class AdminOperationLog(ImmutableAutoIncrementModel):
    """
    Admin operation log model.
    Records important operations performed by admin users.
    """

    __tablename__ = "admin_operation_logs"

    admin_user_id = Column(
        Integer,
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Admin user ID who performed the operation",
    )
    operation_type: Column[str] = Column(
        Enum("CREATE", "UPDATE", "DELETE", "ENABLE", "DISABLE"),
        nullable=False,
        index=True,
        comment="Type of operation",
    )
    resource_type = Column(
        String(50), nullable=False, index=True, comment="Type of resource (user, role, bot, etc.)"
    )
    resource_id = Column(String(100), comment="ID of the affected resource")
    resource_name = Column(String(200), comment="Name of the affected resource")
    operation_desc = Column(String(500), nullable=False, comment="Description of the operation")
    ip_address = Column(INET, comment="IP address of the admin user")
    user_agent = Column(String(500), comment="User agent string")

    # Relationship to admin user
    admin_user = relationship("AdminUser", backref="operation_logs")


class AdminLoginLog(ImmutableAutoIncrementModel):
    """
    Admin login log model.
    Records all login attempts (successful and failed).
    """

    __tablename__ = "admin_login_logs"

    admin_user_id = Column(
        Integer,
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        index=True,
        comment="Admin user ID (NULL for failed logins with invalid username)",
    )
    username = Column(
        String(50), nullable=False, index=True, comment="Username used for login attempt"
    )
    login_result: Column[str] = Column(
        Enum("SUCCESS", "FAILED"), nullable=False, index=True, comment="Result of login attempt"
    )
    ip_address = Column(INET, comment="IP address of login attempt")
    user_agent = Column(String(500), comment="User agent string")
    failure_reason = Column(String(200), comment="Reason for login failure (if applicable)")

    # Relationship to admin user (can be NULL for failed logins)
    admin_user = relationship("AdminUser", backref="login_logs")
