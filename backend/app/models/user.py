"""
User management related models.

This module contains SQLAlchemy models for user accounts, tokens, and login records.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, Integer, String, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB, INET, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from enums import UserType
from models.base import SnowflakeQiaoModel, SnowflakeModel, StatusMixin, Base, SnowflakeIDMixin


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
        Integer,
        nullable=False,
        default=UserType.NORMAL,
        server_default=text("1"),
        comment="User type: 1=normal, 2=official, 3=virtual",
    )

    last_login: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last login time"
    )

    # Indexes - Only essential indexes for MVP
    # Note: phone, email, wechat_openid, apple_id already have unique indexes
    __table_args__ = tuple()


class UserToken(SnowflakeModel):
    """
    User token model.

    Manages JWT tokens with device limits and activity tracking.
    """

    __tablename__ = "user_tokens"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID (redundant for query optimization)"
    )

    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="JWT token")

    device_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Device type: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Device unique identifier"
    )

    platform_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Platform information (JSONB for better performance)"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True, comment="Login IP address")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent string")

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Token expiration time"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Token status: 1=active, 2=revoked",
    )

    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last activity time"
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Token revocation time"
    )

    # Indexes - Only essential indexes for MVP
    # Note: token already has unique index
    __table_args__ = (Index("idx_user_tokens_user_qiao_id", "user_qiao_id"),)


class LoginRecord(Base, SnowflakeIDMixin):
    """
    Login record model.

    Tracks all login attempts for security and analytics purposes.
    Login records are immutable - no updated_at field needed.
    """

    __tablename__ = "login_records"

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="User internal ID")

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="User external ID"
    )

    login_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"), comment="Login attempt time"
    )

    login_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Login method: 1=password, 2=sms, 3=wechat, 4=apple"
    )

    platform: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Platform: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Device identifier"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True, comment="Login IP address")

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="User agent string")

    result: Mapped[int] = mapped_column(Integer, nullable=False, comment="Login result: 1=success, 2=fail")

    fail_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Failure reason")

    token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="Associated JWT token")

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="Login record creation timestamp",
    )
