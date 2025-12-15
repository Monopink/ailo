"""
AI template related models.

This module contains SQLAlchemy models for AI configuration templates.
"""

from typing import TYPE_CHECKING

from markupsafe import escape
from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship
from starlette.requests import Request

from app.core.type_aliases import JSONDict
from app.models.base import AutoIncrementModel, SnowflakeQiaoModel

if TYPE_CHECKING:
    from app.models.ai.personality import AIPersonality
    from app.models.ai.style import AIStyle


class AIType(AutoIncrementModel):
    """
    AI type model for grouping templates and personas.
    """

    __tablename__ = "ai_types"

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Admin-visible name for this AI type",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Description")

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.display_name)}</span>"


class AITemplate(AutoIncrementModel):
    """
    AI template model.

    AI core configuration templates.
    """

    __tablename__ = "ai_templates"

    type_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="AI type ID, references ai_types.id"
    )
    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    prompt_variables: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Prompt variables/placeholder overrides (JSONB for better performance)",
    )

    request_params: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Template-level LLM request parameters (temperature, max_tokens, etc.) - "
            "inherited by instances"
        ),
    )
    llm_config_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="LLM config ID for this template (no FK constraint)",
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Shanghai",
        server_default=text("'Asia/Shanghai'"),
        comment="Default IANA timezone for instantiated instances",
    )

    typing_speed_wpm: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Typing speed (words per minute) applied when instantiating instances",
    )

    # Display name for admin/UI list and association views
    display_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Display name for template"
    )

    position_mapping_config: Mapped[JSONDict | None] = mapped_column(
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

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Selection priority (lower number chosen first)",
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    style: Mapped["AIStyle"] = orm_relationship(
        "AIStyle",
        primaryjoin="AITemplate.style_id == AIStyle.id",
        foreign_keys=[style_id],
        lazy="select",
        viewonly=True,
    )
    personality: Mapped["AIPersonality"] = orm_relationship(
        "AIPersonality",
        primaryjoin="AITemplate.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )
    ai_type: Mapped["AIType"] = orm_relationship(
        "AIType",
        primaryjoin="AITemplate.type_id == AIType.id",
        foreign_keys=[type_id],
        lazy="select",
        viewonly=True,
    )
    llm_config = orm_relationship(
        "LLMConfig",
        lazy="select",
        viewonly=True,
        uselist=False,
        primaryjoin="AITemplate.llm_config_id == foreign(LLMConfig.id)",
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        display = escape(self.display_name) if self.display_name else f"Template {self.id}"
        return f"<span>[{self.id}] {display}</span>"


class AIPersona(SnowflakeQiaoModel):
    """
    AI persona inventory model (SKU-level definition).
    """

    __tablename__ = "ai_personas"

    type_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="AI type association")
    is_reusable: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="1=reusable, 0=single_use",
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="1=active, 2=inactive, 3=used",
    )

    ai_type: Mapped["AIType"] = orm_relationship(
        "AIType",
        primaryjoin="AIPersona.type_id == AIType.id",
        foreign_keys=[type_id],
        lazy="select",
        viewonly=True,
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.qiao_id)}</span>"
