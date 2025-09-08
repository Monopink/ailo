"""
User management related models.

This module contains SQLAlchemy models for user accounts, sessions, and login records.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enums import UserStatus, UserType, DeviceType, LoginType, LoginResult
from models.base import SnowflakeQiaoModel, SnowflakeModel, StatusMixin


class User(SnowflakeQiaoModel, StatusMixin):
    """
    User account model.

    Represents user accounts with various login methods and status tracking.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Username, default to qiao_id"
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, unique=True, comment="Phone number for login"
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, comment="Email address"
    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Password hash"
    )

    wechat_openid: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, comment="WeChat OpenID"
    )

    apple_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, unique=True, comment="Apple ID"
    )

    user_type: Mapped[int] = mapped_column(
        Integer, nullable=False, default=UserType.NORMAL, comment="User type: 1=normal, 2=official, 3=admin"
    )

    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Last login time"
    )

    # Indexes
    __table_args__ = (
        Index("idx_users_qiao_id", "qiao_id"),
        Index("idx_users_phone", "phone"),
        Index("idx_users_email", "email"),
        Index("idx_users_wechat_openid", "wechat_openid"),
        Index("idx_users_apple_id", "apple_id"),
        Index("idx_users_status", "status"),
        Index("idx_users_user_type", "user_type"),
        Index("idx_users_last_login", "last_login"),
        Index("idx_users_created_at", "created_at"),
    )


class UserSession(SnowflakeModel):
    """
    User session model.

    Manages user sessions with device limits and activity tracking.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID (redundant for query optimization)"
    )

    session_token: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, comment="Session token"
    )

    device_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Device type: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Device unique identifier"
    )

    platform_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Platform information (JSONB for better performance)"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, comment="Login IP address")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent string")

    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="Session expiration time"
    )

    is_active: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Session status: 1=active, 2=inactive",
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, comment="Last activity time"
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_sessions_session_token", "session_token"),
        Index("idx_user_sessions_user_id", "user_id"),
        Index("idx_user_sessions_user_qiao_id", "user_qiao_id"),
        Index("idx_user_sessions_device_type", "device_type"),
        Index("idx_user_sessions_expires_at", "expires_at"),
        Index("idx_user_sessions_is_active", "is_active"),
        Index("idx_user_sessions_last_activity", "last_activity_at"),
    )


class LoginRecord(SnowflakeModel):
    """
    Login record model.

    Tracks all login attempts for security and analytics purposes.
    """

    __tablename__ = "login_records"

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="User internal ID")

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="User external ID"
    )

    login_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="Login attempt time")

    login_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Login method: 1=password, 2=sms, 3=wechat, 4=apple"
    )

    platform: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Platform: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Device identifier"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, comment="Login IP address")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent string")

    result: Mapped[int] = mapped_column(Integer, nullable=False, comment="Login result: 1=success, 2=fail")

    fail_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Failure reason")

    session_token: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Associated session token"
    )

    # Indexes
    __table_args__ = (
        Index("idx_login_records_user_id", "user_id"),
        Index("idx_login_records_user_qiao_id", "user_qiao_id"),
        Index("idx_login_records_login_time", "login_time"),
        Index("idx_login_records_login_type", "login_type"),
        Index("idx_login_records_platform", "platform"),
        Index("idx_login_records_result", "result"),
        Index("idx_login_records_ip_address", "ip_address"),
    )
