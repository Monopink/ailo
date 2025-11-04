"""
AI character dimension related models.

This module contains SQLAlchemy models for AI character dimension scores.
"""

from sqlalchemy import BigInteger, Integer, String, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING, Dict, Any

from models.base import SnowflakeModel

if TYPE_CHECKING:
    from models.ai.character import AICharacter
    from models.ai.style import AIDimension, AIStyleDimension, AIRelationship


class AICharacterDimension(SnowflakeModel):
    """
    AI character dimension score model.

    Dimension scoring for each character.
    """

    __tablename__ = "ai_character_dimensions"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Dimension ID, references ai_dimensions.id"
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="Current score value")

    position: Mapped[int] = mapped_column(Integer, nullable=False, comment="Per mille position (0-1000)")

    position_mapping_algorithm: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        server_default=text("1"),
        comment="Position mapping algorithm: 1=direct, 2=V1",
    )

    position_mapping_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Position mapping parameters (JSONB)",
    )

    # Relationships
    character: Mapped["AICharacter"] = relationship(
        "AICharacter",
        primaryjoin="AICharacterDimension.character_id == AICharacter.id",
        foreign_keys=[character_id],
        lazy="select",
        viewonly=True,
    )
    dimension: Mapped["AIDimension"] = relationship(
        "AIDimension",
        primaryjoin="AICharacterDimension.dimension_id == AIDimension.id",
        foreign_keys=[dimension_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes and constraints - Only essential indexes for MVP
    __table_args__ = (
        UniqueConstraint(
            "character_id", "dimension_id", name="ai_character_dimensions_character_id_dimension_id_key"
        ),
        Index("idx_ai_character_dimensions_character_id", "character_id"),
        Index("idx_ai_character_dimensions_dimension_id", "dimension_id"),
    )
