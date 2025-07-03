"""
Social Profile model for contacts_service
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Date, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SocialProfile(Base):
    __tablename__ = "social_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    entity_id = Column(String(36), unique=True, nullable=False)
    entity_type = Column(Integer, nullable=False, default=1, comment="Entity type: 1=user, 2=bot")
    nickname = Column(String(50), comment="Display name for IM")
    avatar_url = Column(String(500), comment="Profile picture URL")
    bio = Column(Text, comment="Bio/description")
    birth_date = Column(Date, comment="Birth date")
    location = Column(String(100), comment="Location")
