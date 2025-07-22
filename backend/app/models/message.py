from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from .base import Base


class MessageHistory(Base):
    __tablename__ = "message_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    message_id = Column(String(255))  # Backend-generated unique message ID
    message_id_client = Column(String(255))  # Client-side message ID for frontend tracking
    from_entity = Column(String(36), nullable=False)
    to_entity = Column(String(36), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="chat")
    message_service = Column(String(36), nullable=False)
    message_time = Column(DateTime)
    status = Column(String(20), default="sent")
    message_metadata = Column(JSON)

    # Explicitly declare columns to be mapped
    __mapper_args__ = {
        "include_properties": [
            "id",
            "created_at",
            "updated_at",
            "message_id",
            "message_id_client",
            "from_entity",
            "to_entity",
            "content",
            "message_type",
            "message_service",
            "message_time",
            "status",
            "message_metadata",
        ]
    }

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_id": self.message_id,
            "message_id_client": self.message_id_client,
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "content": self.content,
            "message_type": self.message_type,
            "message_service": self.message_service,
            "message_time": (self.message_time.isoformat() if self.message_time else None),
            "status": self.status,
            "message_metadata": self.message_metadata,
        }
