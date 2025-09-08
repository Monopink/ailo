"""
AI style and relationship related models.

This module contains SQLAlchemy models for AI styles and relationship configurations.
"""

from typing import Optional
from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import AutoIncrementModel


class AIStyle(AutoIncrementModel):
    """
    AI style model.

    AI style definitions.
    """

    __tablename__ = "ai_styles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Style name")

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Reference count")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Status: 1=active, 2=inactive",
    )

    initial_relationship_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Initial relationship type ID"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_styles_name", "name"),
        Index("idx_ai_styles_status", "status"),
        Index("idx_ai_styles_usage_count", "usage_count"),
    )


class AIRelationshipDimension(AutoIncrementModel):
    """
    AI relationship dimension model.

    Score dimension definitions for AI styles.
    """

    __tablename__ = "ai_relationship_dimensions"

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="Dimension name for LLM response")

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Display name for UI"
    )

    initial_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Initial position, 0-1000 per mille"
    )

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_dimensions_style_id", "style_id"),
        Index("idx_ai_relationship_dimensions_name", "name"),
        Index("idx_ai_relationship_dimensions_status", "status"),
        Index("idx_ai_relationship_dimensions_style_name", "style_id", "name", unique=True),
    )


class AIRelationship(AutoIncrementModel):
    """
    AI relationship model.

    AI relationship type definitions.
    """

    __tablename__ = "ai_relationships"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Relationship name")

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    prompt_fragment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Prompt fragment for this relationship type"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Usage count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationships_name", "name"),
        Index("idx_ai_relationships_status", "status"),
        Index("idx_ai_relationships_usage_count", "usage_count"),
    )


class AIRelationshipIndex(AutoIncrementModel):
    """
    AI relationship index model.

    Mapping from score ranges to relationship types.
    """

    __tablename__ = "ai_relationship_indexes"

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Dimension ID, references ai_relationship_dimensions.id"
    )

    dimension_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="Dimension name")

    start_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Start position, 0-1000 per mille"
    )

    end_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="End position, 0-1000 per mille"
    )

    relationship_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Relationship ID, references ai_relationships.id"
    )

    priority: Mapped[int] = mapped_column(Integer, nullable=False, comment="Priority level")

    limit_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Maximum occurrence count, NULL means unlimited"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_indexes_style_id", "style_id"),
        Index("idx_ai_relationship_indexes_dimension_id", "dimension_id"),
        Index("idx_ai_relationship_indexes_dimension_name", "dimension_name"),
        Index("idx_ai_relationship_indexes_relationship_id", "relationship_id"),
        Index("idx_ai_relationship_indexes_position_range", "start_position", "end_position"),
        Index("idx_ai_relationship_indexes_priority", "priority"),
        Index(
            "idx_ai_relationship_indexes_style_dimension",
            "style_id",
            "dimension_name",
            "start_position",
            "end_position",
            unique=True,
        ),
    )
