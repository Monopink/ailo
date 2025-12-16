"""
AI personality related models.

This module contains SQLAlchemy models for AI personality templates and placeholders.
"""

from markupsafe import escape
from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.requests import Request

from app.models.base import AutoIncrementModel
from app.type_defs import JSONDict


class AIPersonality(AutoIncrementModel):
    """
    AI personality model.

    AI personality templates.
    """

    __tablename__ = "ai_personalities"

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="Personality prompt template")

    json_schema: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="JSON schema definition (JSONB for better performance)"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.display_name)}</span>"


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

    display_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Display name for UI"
    )

    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Placeholder description"
    )

    example_value: Mapped[str | None] = mapped_column(
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
