"""
AI template related models.

This module contains SQLAlchemy models for AI configuration templates.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel, SnowflakeQiaoModel

if TYPE_CHECKING:
    from models.ai.style import AIStyle
    from models.ai.personality import AIPersonality


class AICharacterTemplate(AutoIncrementModel):
    """
    AI character template model.

    AI core configuration templates.
    """

    __tablename__ = "ai_character_templates"

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

    request_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Template-level LLM request parameters (temperature, max_tokens, etc.) - inherited by character instances",
    )

    typing_speed_wpm: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Typing speed (words per minute) applied when instantiating characters",
    )

    # Display name for admin/UI list and association views
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Display name for character template"
    )

    position_mapping_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Per-dimension position mapping configuration",
    )

    is_reusable: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Is reusable: 1=reusable, 0=single_use",
    )

    profile_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Associated profile template count",
    )

    profile_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Associated profile template ID (for single-use)"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        primaryjoin="AICharacterTemplate.style_id == AIStyle.id",
        foreign_keys=[style_id],
        lazy="select",
        viewonly=True,
    )
    personality: Mapped["AIPersonality"] = relationship(
        "AIPersonality",
        primaryjoin="AICharacterTemplate.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )
    profile: Mapped[Optional["AIProfileTemplate"]] = relationship(
        "AIProfileTemplate",
        primaryjoin="AICharacterTemplate.profile_id == AIProfileTemplate.id",
        foreign_keys=[profile_id],
        lazy="select",
        viewonly=True,
    )


class AIProfileTemplate(SnowflakeQiaoModel):
    """
    AI profile template model.

    AI social profile templates.
    """

    __tablename__ = "ai_profile_templates"

    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Category")

    character_template_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Associated character template ID, references ai_character_templates.id"
    )

    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Nickname")

    gender: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Avatar URL")

    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Bio/description")

    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Region/location")

    is_reusable: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Is reusable: 1=reusable, 0=single_use",
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    character_template: Mapped["AICharacterTemplate"] = relationship(
        "AICharacterTemplate",
        primaryjoin="AIProfileTemplate.character_template_id == AICharacterTemplate.id",
        foreign_keys=[character_template_id],
        lazy="select",
        viewonly=True,
    )
