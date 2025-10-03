"""
AI template related models.

This module contains SQLAlchemy models for AI configuration templates.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Text, Index, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel, SnowflakeQiaoModel

if TYPE_CHECKING:
    from models.ai.style import AIStyle
    from models.ai.personality import AIPersonality


class AIInfoTemplate(AutoIncrementModel):
    """
    AI info template model.

    AI core configuration templates.
    """

    __tablename__ = "ai_info_templates"

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Memory settings")

    prompt_variables: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Prompt variables/placeholder overrides (JSONB for better performance)",
    )

    score_offset_algorithm: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Score offset algorithm (enum int)"
    )

    score_offset_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Score offset parameters (JSONB)"
    )

    is_reusable: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Is reusable: 1=reusable, 0=single_use"
    )

    profile_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Associated profile template count"
    )

    profile_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Associated profile template ID (for single-use)"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        primaryjoin="AIInfoTemplate.style_id == AIStyle.id",
        foreign_keys=[style_id],
        lazy="select",
        viewonly=True,
    )
    personality: Mapped["AIPersonality"] = relationship(
        "AIPersonality",
        primaryjoin="AIInfoTemplate.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )
    profile: Mapped[Optional["AIProfileTemplate"]] = relationship(
        "AIProfileTemplate",
        primaryjoin="AIInfoTemplate.profile_id == AIProfileTemplate.id",
        foreign_keys=[profile_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_info_templates_style_id", "style_id"),
        Index("idx_ai_info_templates_personality_id", "personality_id"),
        Index("idx_ai_info_templates_status", "status"),
        Index("idx_ai_info_templates_is_reusable", "is_reusable"),
    )


class AIProfileTemplate(SnowflakeQiaoModel):
    """
    AI profile template model.

    AI social profile templates.
    """

    __tablename__ = "ai_profile_templates"

    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Category")

    info_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Associated info template ID, references ai_info_templates.id"
    )

    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Nickname")

    gender: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Avatar URL")

    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Bio/description")

    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Region/location")

    is_reusable: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Is reusable: 1=reusable, 0=single_use"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    info: Mapped["AIInfoTemplate"] = relationship(
        "AIInfoTemplate",
        primaryjoin="AIProfileTemplate.info_id == AIInfoTemplate.id",
        foreign_keys=[info_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_profile_templates_category", "category"),
        Index("idx_ai_profile_templates_info_id", "info_id"),
        Index("idx_ai_profile_templates_nickname", "nickname"),
        Index("idx_ai_profile_templates_status", "status"),
        Index("idx_ai_profile_templates_is_reusable", "is_reusable"),
    )
