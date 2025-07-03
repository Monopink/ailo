"""
Contact model for contacts_service
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    user_entity_id = Column(String(36), nullable=False, comment="User ID")
    contact_entity_id = Column(String(36), nullable=False, comment="Contact ID (user or bot)")
    contact_type = Column(Integer, nullable=False, default=1, comment="Contact type: 1=user, 2=bot")
    status = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Contact status: 1=normal, 2=blocked, 3=deleted, 4=muted",
    )
    is_pinned = Column(Boolean, default=False, comment="Is pinned")
    last_message_time = Column(DateTime, comment="Last message time")
    unread_count = Column(Integer, default=0, comment="Unread message count")
    remark = Column(String(100), comment="Remark name")
