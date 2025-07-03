from sqlalchemy import Column, Integer, String, DateTime, func, VARCHAR, Boolean, Text, Date, JSON
from ..db.base_class import Base

# If Base is defined in each model, this might not be needed.
# But assuming a central Base class.
# Base = declarative_base() # This might be replaced by the import


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(VARCHAR(36), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=True)
    email = Column(String(100), unique=True, nullable=True)
    phone = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    last_login = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")  # 用户状态字段：'active', 'inactive', 'suspended', etc.
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    # IM user fields (matching database schema)
    nickname = Column(String(50))
    avatar_url = Column(String(500))
    bio = Column(Text)
    birth_date = Column(Date)
    location = Column(String(100))
    timezone = Column(String(50), default="Asia/Shanghai")
    language_preference = Column(String(10), default="zh-CN")
    notification_settings = Column(JSON)
    privacy_settings = Column(JSON)
    last_active_at = Column(DateTime)
    is_verified = Column(Boolean, default=False)
    verification_type = Column(String(10), default="none")
    subscription_type = Column(String(10), default="free")
    subscription_expires_at = Column(DateTime)
