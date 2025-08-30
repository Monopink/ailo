"""
AI style and relationship related models.

This module contains SQLAlchemy models for AI styles and relationship configurations.
"""

from typing import List, Optional
from sqlalchemy import Integer, String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import AutoIncrementModel


class AIStyle(AutoIncrementModel):
    """
    AI style model.

    AI style and scoring dimension definitions.
    """

    __tablename__ = "ai_styles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Style name")

    score_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of scoring dimensions"
    )

    score_name: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, comment="Scoring dimension names (JSON)"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Reference count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_styles_name", "name"),
        Index("idx_ai_styles_score_count", "score_count"),
        Index("idx_ai_styles_status", "status"),
        Index("idx_ai_styles_usage_count", "usage_count"),
    )


class AIRelationship(AutoIncrementModel):
    """
    AI relationship model.

    AI relationship type definitions.
    """

    __tablename__ = "ai_relationships"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Relationship name")

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

    score_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="Score dimension order")

    score_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Score name")

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
        Index("idx_ai_relationship_indexes_score_order", "score_order"),
        Index("idx_ai_relationship_indexes_score_name", "score_name"),
        Index("idx_ai_relationship_indexes_relationship_id", "relationship_id"),
        Index("idx_ai_relationship_indexes_position_range", "start_position", "end_position"),
        Index("idx_ai_relationship_indexes_priority", "priority"),
    )
