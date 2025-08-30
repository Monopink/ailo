"""
AI relationship score related models.

This module contains SQLAlchemy models for AI relationship scoring and statistics.
"""

from sqlalchemy import BigInteger, Integer, String, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from models.base import SnowflakeModel


class AIRelationshipScore(SnowflakeModel):
    """
    AI relationship score model.

    AI relationship scoring for each character.
    """

    __tablename__ = "ai_relationship_scores"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    score_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="Score dimension order")

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="Current score value")

    score_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="Starting score value")

    score_end: Mapped[int] = mapped_column(Integer, nullable=False, comment="Ending score value")

    score_offset_algorithm: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Score offset algorithm"
    )

    score_offset_coefficient: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Score offset coefficient"
    )

    score_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Per mille position (0-1000)"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_scores_character_id", "character_id"),
        Index("idx_ai_relationship_scores_score_order", "score_order"),
        Index("idx_ai_relationship_scores_score_position", "score_position"),
    )


class AIRelationshipCount(SnowflakeModel):
    """
    AI relationship count model.

    AI relationship type usage statistics.
    """

    __tablename__ = "ai_relationship_counts"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    relationship_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Relationship ID, references ai_relationship.id"
    )

    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Usage count")

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_counts_character_id", "character_id"),
        Index("idx_ai_relationship_counts_relationship_id", "relationship_id"),
        Index("idx_ai_relationship_counts_count", "count"),
    )
