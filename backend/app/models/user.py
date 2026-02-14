"""User management related models.

This module contains SQLAlchemy models for user accounts, tokens, and login records.
"""

from datetime import datetime
from uuid import UUID

from markupsafe import escape
from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.requests import Request

from app.enums import UserType
from app.models.base import Base, SnowflakeIDMixin, SnowflakeModel, SnowflakeQiaoModel, StatusMixin
from app.type_defs import JSONDict


class User(SnowflakeQiaoModel, StatusMixin):
    """User account model.

    Represents user accounts with various login methods and status tracking.
    """

    __tablename__ = "users"

    username: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="User-customizable ID, NULL if not set"
    )

    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True, comment="Phone number for login"
    )

    email: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, comment="Email address"
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Password hash"
    )

    is_verified: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Real-name verification status: 1=verified, 0=unverified",
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Verification approval time"
    )

    verify_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Verification source (e.g., public_security, alipay, wechat, tencentcloud)",
    )

    verification_info: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Verification extra info (JSON)"
    )

    user_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=UserType.NORMAL,
        server_default=text("1"),
        comment="User type: 1=normal, 2=official, 3=virtual",
    )

    needs_profile_setup: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether the user must complete profile setup before entering the main app",
    )

    last_login: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last login time"
    )

    # Indexes - Only essential indexes for MVP
    # Note: phone, email already have unique indexes
    __table_args__ = ()

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.qiao_id)} / {escape(self.username)}</span>"


class UserToken(SnowflakeModel):
    """User token model.

    Manages JWT tokens with device limits and activity tracking.
    """

    __tablename__ = "user_tokens"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID (redundant for query optimization)"
    )

    access_token: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, comment="Access JWT token"
    )

    device_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Device type: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, comment="Device unique identifier (UUID)"
    )

    platform_info: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Platform information (JSONB for better performance)"
    )

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True, comment="Login IP address")

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="User agent string")

    access_expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Access token expiration time"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Token status: 1=active, 2=revoked",
    )

    last_activity_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last activity time"
    )

    access_revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Access token revocation time"
    )

    refresh_token_hash: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Refresh token hash (SHA-256)"
    )

    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Refresh token expiration time"
    )

    refresh_revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Refresh token revocation time"
    )

    token_metadata: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional metadata (refresh counters, device info, etc.)",
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="UserToken.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        Index("idx_user_tokens_user_qiao_id", "user_qiao_id"),
        Index(
            "idx_user_tokens_refresh_hash",
            "refresh_token_hash",
            unique=True,
            postgresql_where=text("refresh_token_hash IS NOT NULL"),
        ),
    )


class UserAuth(SnowflakeModel, StatusMixin):
    """Third-party identity binding model.

    Stores stable mapping between internal users and external identity providers
    (WeChat/Apple/QQ etc.). Does NOT store login sessions/tokens.
    """

    __tablename__ = "user_auths"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User internal ID")

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID (redundant for query optimization)"
    )

    auth_type: Mapped[int] = mapped_column(Integer, nullable=False, comment="Auth provider type")

    provider_uid: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Provider user unique ID (openid/sub/open_id/user_id)"
    )

    unionid: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="WeChat unionid (optional)"
    )

    app_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Provider app ID")

    extra_data: Mapped[JSONDict | None] = mapped_column(JSONB, nullable=True, comment="Extra info")

    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Unbind time"
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="UserAuth.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("auth_type", "provider_uid", name="uq_user_auths_type_provider"),
        Index("idx_user_auths_user_qiao_id", "user_qiao_id"),
    )


class LoginRecord(Base, SnowflakeIDMixin):
    """Login record model.

    Tracks all login attempts for security and analytics purposes.
    Login records are immutable - no updated_at field needed.
    """

    __tablename__ = "login_records"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="User internal ID"
    )

    user_qiao_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="User external ID"
    )

    login_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="Login attempt time",
    )

    login_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Login method: 1=password, 2=sms, 3=wechat, 4=apple"
    )

    platform: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Platform: 1=ios, 2=android, 3=web, 4=mini_program"
    )

    device_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, comment="Device identifier (UUID)"
    )

    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True, comment="Login IP address")

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="User agent string")

    result: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Login result: 1=success, 2=fail"
    )

    fail_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Failure reason"
    )

    user_token_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated session ID (references user_tokens.id on successful login)",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="Login record creation timestamp",
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="LoginRecord.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )

    user_token: Mapped["UserToken | None"] = relationship(
        "UserToken",
        primaryjoin="LoginRecord.user_token_id == UserToken.id",
        foreign_keys=[user_token_id],
        lazy="select",
        viewonly=True,
    )
