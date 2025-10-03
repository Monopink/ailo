"""
AI relationship score related models.

This module contains SQLAlchemy models for AI relationship scoring and statistics.
"""

from sqlalchemy import BigInteger, Integer, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, TYPE_CHECKING

from models.base import SnowflakeModel

if TYPE_CHECKING:
    from models.ai.character import AICharacter
    from models.ai.style import AIRelationshipDimension, AIRelationship


class AIRelationshipScore(SnowflakeModel):
    """
    AI relationship score model.

    AI relationship scoring for each character.
    """

    __tablename__ = "ai_relationship_scores"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Dimension ID, references ai_relationship_dimensions.id"
    )

    dimension_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="Dimension name")

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="Current score value")

    position: Mapped[int] = mapped_column(Integer, nullable=False, comment="Per mille position (0-1000)")

    relationship_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Current relationship type ID"
    )

    relationship_display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Relationship display name"
    )

    relationship_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, default={}, comment="Relationship usage counts (JSONB)"
    )

    # Relationships
    character: Mapped["AICharacter"] = relationship(
        "AICharacter",
        primaryjoin="AIRelationshipScore.character_id == AICharacter.id",
        foreign_keys=[character_id],
        lazy="select",
        viewonly=True,
    )
    dimension: Mapped["AIRelationshipDimension"] = relationship(
        "AIRelationshipDimension",
        primaryjoin="AIRelationshipScore.dimension_id == AIRelationshipDimension.id",
        foreign_keys=[dimension_id],
        lazy="select",
        viewonly=True,
    )
    relationship: Mapped[Optional["AIRelationship"]] = relationship(
        "AIRelationship",
        primaryjoin="AIRelationshipScore.relationship_id == AIRelationship.id",
        foreign_keys=[relationship_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_scores_character_id", "character_id"),
        Index("idx_ai_relationship_scores_dimension_id", "dimension_id"),
        Index("idx_ai_relationship_scores_dimension_name", "dimension_name"),
        Index("idx_ai_relationship_scores_score", "score"),
        Index("idx_ai_relationship_scores_position", "position"),
        Index("idx_ai_relationship_scores_relationship_id", "relationship_id"),
        Index(
            "idx_ai_relationship_scores_character_dimension", "character_id", "dimension_name", unique=True
        ),
    )
