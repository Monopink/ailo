from sqlalchemy import Column, Integer, String, DateTime, func, Boolean, JSON, Enum
from ..db.base_class import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(String(20), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=True)
    email = Column(String(100), unique=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    timezone = Column(String(50), default="Asia/Shanghai", comment="Timezone")
    language_preference = Column(String(10), default="zh-CN", comment="Preferred language")
    last_active_at = Column(DateTime, nullable=True, comment="Last activity timestamp")
    last_login = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")
    role = Column(String(20), default="user")
    language = Column(String(10), default="zh")
    area = Column(String(100), default="China")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    # Account related fields
    is_verified = Column(Boolean, default=False)
    verification_type = Column(Enum("phone", "email", "none", name="verification_type"), default="none")
    subscription_type = Column(Enum("free", "premium", "vip", name="subscription_type"), default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    # Settings (reserved for future use)
    notification_settings = Column(JSON, nullable=True)
    privacy_settings = Column(JSON, nullable=True)
    # Contact management settings
    contact_limit = Column(Integer, default=3, comment="Contact limit for user")
    search_display_limit = Column(
        Integer, default=2, comment="Number of contacts to display in search results"
    )
