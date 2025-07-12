"""
User model for contacts_service
Used to access user information including contact limits
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, Boolean
from sqlalchemy.sql import func
from .base import Base


class User(Base):
    """User model - read-only access to users table for contact limits"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    entity_id = Column(String(20), unique=True, nullable=False)
    username = Column(String(50), unique=True)
    email = Column(String(100), unique=True)
    password_hash = Column(String(255), nullable=False)
    last_login = Column(DateTime)
    status = Column(String(20), default="active")
    role = Column(String(20), default="user")
    language = Column(String(10), default="zh")
    area = Column(String(100), default="China")
    phone = Column(String(20), unique=True)

    # Account related fields
    last_active_at = Column(DateTime)
    is_verified = Column(Boolean, default=False)
    verification_type = Column(
        Enum("phone", "email", "none", name="verification_type_enum"), default="none"
    )
    subscription_type = Column(
        Enum("free", "premium", "vip", name="subscription_type_enum"), default="free"
    )
    subscription_expires_at = Column(DateTime)

    # Settings
    timezone = Column(String(50), default="Asia/Shanghai")
    language_preference = Column(String(10), default="zh-CN")
    notification_settings = Column(JSON)
    privacy_settings = Column(JSON)

    # Contact management settings
    contact_limit = Column(Integer, default=3)
    search_display_limit = Column(Integer, default=2)
