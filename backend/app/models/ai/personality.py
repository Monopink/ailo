"""
AI personality related models.

This module contains SQLAlchemy models for AI personality templates and placeholders.
"""

from typing import Any, Dict, Optional
from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import AutoIncrementModel


class AIPersonality(AutoIncrementModel):
    """
    AI personality model.

    AI personality templates.
    """

    __tablename__ = "ai_personalities"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Personality name")

    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="Personality prompt template")

    json_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="JSON schema definition (JSONB for better performance)"
    )

    typing_speed: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Typing speed in characters per minute"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Reference count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_personalities_name", "name"),
        Index("idx_ai_personalities_status", "status"),
        Index("idx_ai_personalities_usage_count", "usage_count"),
    )


class AIPersonalityPlaceholder(AutoIncrementModel):
    """
    AI personality placeholder model.

    Personality template placeholders.
    """

    __tablename__ = "ai_personality_placeholders"

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    placeholder_key: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Placeholder key name"
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Display name for UI"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Placeholder description"
    )

    example_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Example placeholder value"
    )

    # Keep additional fields for enhanced functionality
    placeholder_type: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Placeholder type: 1=text, 2=number, 3=boolean, 4=list"
    )

    validation_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Validation rules (JSONB for better performance)"
    )

    is_required: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Is required: 1=required, 0=optional"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_personality_placeholders_personality_id", "personality_id"),
        Index("idx_ai_personality_placeholders_placeholder_key", "placeholder_key"),
        Index("idx_ai_personality_placeholders_placeholder_type", "placeholder_type"),
        Index("idx_ai_personality_placeholders_is_required", "is_required"),
        Index("idx_ai_personality_placeholders_display_name", "display_name"),
    )
