"""
Bot Template model for contacts_service
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Date, Index, func
from .base import Base


class BotTemplate(Base):
    __tablename__ = "bot_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    template_id = Column(String(10), unique=True, nullable=False)
    template_status = Column(String(20), default="active", comment="Template status: active, disabled")
    template_type = Column(String(20), default="full", comment="Template type: full, persona_info")
    weight = Column(
        Integer, default=100, comment="Weight for random selection, higher values have higher probability"
    )
    remaining_uses = Column(Integer, default=-1, comment="Remaining usage count, -1 means unlimited")
    max_uses = Column(Integer, default=-1, comment="Maximum usage count, -1 means unlimited")
    model = Column(String(50), nullable=False)
    gender = Column(String(10), nullable=False)
    birthday = Column(DateTime)
    birth_date = Column(Date)
    timezone = Column(String(50), default="Asia/Shanghai")
    city_name = Column(String(100))
    friend_score = Column(Integer, default=0)
    romance_score = Column(Integer, default=0)
    friend_score_cap = Column(Integer, default=5000)
    friend_score_floor = Column(Integer, default=0)
    romance_score_cap = Column(Integer, default=5000)
    friend_score_pos_k = Column(Integer, default=1200)
    friend_score_neg_k = Column(Integer, default=120)
    romance_score_k = Column(Integer, default=1200)
    friend_config = Column(JSON)
    romance_config = Column(JSON)
    override_config = Column(JSON)
    is_polite = Column(Boolean, default=True)
    is_crushing = Column(Boolean, default=False)
    emotions_config = Column(JSON)
    info = Column(Text)
    memory = Column(Text)
    nickname = Column(String(50))
    avatar_url = Column(String(500))
    bio = Column(Text)
    location = Column(String(100))

    # Define indexes
    __table_args__ = (
        Index("idx_template_id", "template_id"),
        Index("idx_template_status", "template_status"),
        Index("idx_weight", "weight"),
        Index("idx_remaining_uses", "remaining_uses"),
    )

    def __repr__(self):
        return f"<BotTemplate(id={self.id}, template_id={self.template_id}, nickname={self.nickname}, status={self.template_status})>"
