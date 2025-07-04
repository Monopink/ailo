"""
User model for bot_message_service.
"""

from sqlalchemy import Column, Integer, String, DateTime
from ..base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    entity_id = Column(String(36), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    last_login = Column(DateTime)
    status = Column(String(20), default="active")
    role = Column(String(20), default="user")
    language = Column(String(10), default="zh")
    area = Column(String(100), default="China")
    phone = Column(String(20))
