"""
AI template related models.

This module contains SQLAlchemy models for AI configuration templates.
"""

from typing import Any, Dict, Optional
from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import AutoIncrementModel


class AIInfoTemplate(AutoIncrementModel):
    """
    AI info template model.

    AI core configuration templates.
    """

    __tablename__ = "ai_info_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Template name")

    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="Core prompt template")

    json_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="JSON schema definition (JSONB for better performance)"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Reference count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_info_templates_name", "name"),
        Index("idx_ai_info_templates_status", "status"),
        Index("idx_ai_info_templates_usage_count", "usage_count"),
    )


class AIProfileTemplate(AutoIncrementModel):
    """
    AI profile template model.

    AI social profile templates.
    """

    __tablename__ = "ai_profile_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Template name")

    nickname_template: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Nickname generation template"
    )

    bio_template: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Bio generation template"
    )

    avatar_template: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Avatar generation template"
    )

    gender_template: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Gender assignment template"
    )

    age_template: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Age assignment template"
    )

    location_template: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Location assignment template"
    )

    json_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="JSON schema definition (JSONB for better performance)"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Reference count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_profile_templates_name", "name"),
        Index("idx_ai_profile_templates_status", "status"),
        Index("idx_ai_profile_templates_usage_count", "usage_count"),
    )
