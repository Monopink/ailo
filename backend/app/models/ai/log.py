"""
AI request log related models.

This module contains SQLAlchemy models for AI service request logging.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, DateTime, text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import ImmutableSnowflakeModel


class AIRequestLog(ImmutableSnowflakeModel):
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

    request_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="production",
        server_default=text("'production'"),
        comment="Request type: production or test",
    )

    provider_name: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="LLM provider name (doubao, openai, etc.)"
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Model name used for the request"
    )

    llm_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="LLM config ID used for this request"
    )

    response_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Provider response ID (for caching trace)"
    )

    cache_hit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Whether the provider reported cached tokens",
    )

    buffer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Associated ai_message_buffer.id that triggered the request"
    )

    request: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, comment="Request content")

    response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Response content"
    )

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Request status: 1=success, 2=failed, 3=timeout"
    )

    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Token consumption")

    response_time: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Request completion timestamp"
    )
