"""
AI request log related models.

This module contains SQLAlchemy models for AI service request logging.
"""

from typing import Optional
from datetime import datetime
from sqlalchemy import BigInteger, Integer, Text, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, SnowflakeIDMixin


class AIRequestLog(Base, SnowflakeIDMixin):
    """
    AI request log model.

    AI service request logging.
    AI request logs are immutable - no updated_at field needed.
    """

    __tablename__ = "ai_request_logs"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User ID, references users.id")

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    request: Mapped[str] = mapped_column(Text, nullable=False, comment="Request content (JSON)")

    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Response content (JSON)")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Request status: 1=success, 2=failed, 3=timeout"
    )

    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Token consumption")

    response_time: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), comment="Request log creation timestamp"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_request_logs_character_id", "character_id"),
        Index("idx_ai_request_logs_user_id", "user_id"),
        Index("idx_ai_request_logs_style_id", "style_id"),
        Index("idx_ai_request_logs_personality_id", "personality_id"),
        Index("idx_ai_request_logs_status", "status"),
        Index("idx_ai_request_logs_created_at", "created_at"),
    )
