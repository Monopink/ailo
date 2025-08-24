"""
AI style and relationship related models.

This module contains SQLAlchemy models for AI styles and relationship configurations.
"""

from typing import List
from sqlalchemy import Integer, String, JSON, Index
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

    description: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Relationship description"
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

    score_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="Score range start")

    score_end: Mapped[int] = mapped_column(Integer, nullable=False, comment="Score range end")

    relationship_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Relationship ID, references ai_relationships.id"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_indexes_style_id", "style_id"),
        Index("idx_ai_relationship_indexes_score_order", "score_order"),
        Index("idx_ai_relationship_indexes_relationship_id", "relationship_id"),
        Index("idx_ai_relationship_indexes_score_range", "score_start", "score_end"),
    )
