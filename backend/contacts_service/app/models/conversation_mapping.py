"""
Conversation Mapping model for contacts_service
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ConversationMapping(Base):
    __tablename__ = "conversation_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    user_entity_id = Column(String(36), nullable=False)
    contact_entity_id = Column(String(36), nullable=False)
    contact_type = Column(Integer, nullable=False, default=1, comment="Contact type: 1=user, 2=bot")
    im_service_type = Column(
        Integer, nullable=False, default=1, comment="IM service type: 1=leancloud, 2=websocket, 3=custom"
    )
    conversation_id = Column(
        String(100), comment="LeanCloud system conversation ID or other service conversation ID"
    )
    service_metadata = Column(JSON, comment="Service specific metadata")
    is_active = Column(Boolean, default=True)
