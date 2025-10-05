"""
AI style and relationship related models.

This module contains SQLAlchemy models for AI styles and relationship configurations.
"""

from typing import Optional, List
from sqlalchemy import Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

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

    # Relationships
    dimensions: Mapped[List["AIRelationshipDimension"]] = relationship(
        "AIRelationshipDimension",
        back_populates="style",
        primaryjoin="AIStyle.id == foreign(AIRelationshipDimension.style_id)",
        cascade="all, delete-orphan",
    )

    relationship_indexes: Mapped[List["AIRelationshipIndex"]] = relationship(
        "AIRelationshipIndex",
        back_populates="style",
        primaryjoin="AIStyle.id == foreign(AIRelationshipIndex.style_id)",
        cascade="all, delete-orphan",
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

    Position dimension definitions for AI styles.
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

    # Relationships
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        back_populates="dimensions",
        primaryjoin="foreign(AIRelationshipDimension.style_id) == AIStyle.id",
    )

    relationship_indexes: Mapped[List["AIRelationshipIndex"]] = relationship(
        "AIRelationshipIndex",
        back_populates="dimension",
        primaryjoin="AIRelationshipDimension.id == foreign(AIRelationshipIndex.dimension_id)",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_dimensions_style_id", "style_id"),
        Index("idx_ai_relationship_dimensions_name", "name"),
        Index("idx_ai_relationship_dimensions_style_name", "style_id", "name", unique=True),
    )


class AIRelationship(AutoIncrementModel):
    """
    AI relationship model.

    AI relationship type definitions.
    """

    __tablename__ = "ai_relationships"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, comment="Relationship name (unique identifier)"
    )

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    prompt_fragment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Prompt fragment for this relationship type"
    )

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Usage count")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )

    # Relationships
    relationship_indexes: Mapped[List["AIRelationshipIndex"]] = relationship(
        "AIRelationshipIndex",
        back_populates="relationship",
        primaryjoin="AIRelationship.id == foreign(AIRelationshipIndex.relationship_id)",
        cascade="all, delete-orphan",
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

    Mapping from position ranges to relationship types.
    """

    __tablename__ = "ai_relationship_indexes"

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Dimension ID, references ai_relationship_dimensions.id",
    )

    start_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Start position, 0-1000 per mille"
    )

    end_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="End position, 0-1000 per mille"
    )

    relationship_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Relationship ID, references ai_relationships.id",
    )

    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", comment="Priority level (default: 1)"
    )

    limit_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Maximum occurrence count, NULL means unlimited"
    )

    # Relationships
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        back_populates="relationship_indexes",
        primaryjoin="foreign(AIRelationshipIndex.style_id) == AIStyle.id",
    )

    dimension: Mapped["AIRelationshipDimension"] = relationship(
        "AIRelationshipDimension",
        back_populates="relationship_indexes",
        primaryjoin="foreign(AIRelationshipIndex.dimension_id) == AIRelationshipDimension.id",
    )

    relationship: Mapped["AIRelationship"] = relationship(
        "AIRelationship",
        back_populates="relationship_indexes",
        primaryjoin="foreign(AIRelationshipIndex.relationship_id) == AIRelationship.id",
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_relationship_indexes_style_id", "style_id"),
        Index("idx_ai_relationship_indexes_dimension_id", "dimension_id"),
        Index("idx_ai_relationship_indexes_relationship_id", "relationship_id"),
        Index("idx_ai_relationship_indexes_position_range", "start_position", "end_position"),
        Index("idx_ai_relationship_indexes_priority", "priority"),
        Index(
            "idx_ai_relationship_indexes_style_dimension",
            "style_id",
            "dimension_id",
            "start_position",
            "end_position",
            unique=True,
        ),
    )
