"""
Template Mapping Model - Maps users to bot templates with search tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from .base import Base


class TemplateMapping(Base):
    __tablename__ = "template_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    status = Column(String(20), default="active", comment="Mapping status: active, inactive")
    entity_id = Column(
        String(20), unique=True, nullable=False, comment="Generated unique entity_id for this mapping"
    )
    user_entity_id = Column(String(20), nullable=False, comment="User who can see this template")
    template_id = Column(String(10), nullable=False, comment="Reference to bot_templates.template_id")
    last_search_time = Column(
        DateTime, nullable=True, comment="Last time this mapping appeared in search results"
    )

    # Define indexes
    __table_args__ = (
        Index("idx_user_template", "user_entity_id", "template_id"),
        Index("idx_entity_id", "entity_id"),
        Index("idx_last_search_time", "last_search_time"),
        Index("idx_status", "status"),
        Index("uk_user_template", "user_entity_id", "template_id", unique=True),
    )

    def __repr__(self):
        return f"<TemplateMapping(id={self.id}, entity_id={self.entity_id}, user_entity_id={self.user_entity_id}, template_id={self.template_id})>"
