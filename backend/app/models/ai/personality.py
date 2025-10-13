"""
AI personality related models.

This module contains SQLAlchemy models for AI personality templates and placeholders.
"""

from typing import Any, Dict, Optional
from sqlalchemy import Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel


class AIPersonality(AutoIncrementModel):
    """
    AI personality model.

    AI personality templates.
    """

    __tablename__ = "ai_personalities"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Personality name")

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="Personality prompt template")

    json_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="JSON schema definition (JSONB for better performance)"
    )

    usage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Reference count"
    )

    typing_speed: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Typing speed in characters per minute"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Constraints
    __table_args__ = (UniqueConstraint("name", name="ai_personalities_name_key"),)


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

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name for UI")

    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Placeholder description"
    )

    example_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Example placeholder value"
    )

    is_required: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is required: 1=required, 0=optional",
    )

    # Relationships
    personality: Mapped["AIPersonality"] = relationship(
        "AIPersonality",
        primaryjoin="AIPersonalityPlaceholder.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )
