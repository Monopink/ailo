"""
AI style and relationship related models.

This module contains SQLAlchemy models for AI styles and relationship configurations.
"""

from typing import Optional, List
from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel


class AIStyle(AutoIncrementModel):
    """
    AI style model.

    AI style definitions.
    """

    __tablename__ = "ai_styles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Style name")

    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Relationships
    style_dimensions: Mapped[List["AIStyleDimension"]] = relationship(
        "AIStyleDimension",
        back_populates="style",
        primaryjoin="AIStyle.id == foreign(AIStyleDimension.style_id)",
        cascade="all, delete-orphan",
    )

    # Constraints
    __table_args__ = (UniqueConstraint("name", name="ai_styles_name_key"),)


    def __admin_select2_repr__(self, request) -> str:
        from markupsafe import escape
        return f"<span>[{self.id}] {escape(self.display_name)}</span>"


class AIDimension(AutoIncrementModel):
    """
    AI dimension model.

    Dimension definitions (e.g., "extroversion-introversion", "rational-emotional").
    """

    __tablename__ = "ai_dimensions"

    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="Dimension name for LLM response (globally unique)"
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Display name for UI"
    )

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Dimension description")

    # Relationships
    style_dimensions: Mapped[List["AIStyleDimension"]] = relationship(
        "AIStyleDimension",
        back_populates="dimension",
        primaryjoin="AIDimension.id == foreign(AIStyleDimension.dimension_id)",
        cascade="all, delete-orphan",
    )

    relationship_mappings: Mapped[List["AIDimensionRelationshipMapping"]] = relationship(
        "AIDimensionRelationshipMapping",
        back_populates="dimension",
        primaryjoin="AIDimension.id == foreign(AIDimensionRelationshipMapping.dimension_id)",
        cascade="all, delete-orphan",
    )

    def __admin_select2_repr__(self, request) -> str:
        from markupsafe import escape
        display = escape(self.display_name) if self.display_name else escape(self.name)
        return f"<span>[{self.id}] {display}</span>"


class AIStyleDimension(AutoIncrementModel):
    """
    AI style dimension model.

    Style-specific dimension configurations (many-to-many relationship between styles and dimensions).
    """

    __tablename__ = "ai_style_dimensions"

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Dimension ID, references ai_dimensions.id"
    )

    initial_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Initial position for this style, 0-1000 per mille"
    )

    # Relationships
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        back_populates="style_dimensions",
        primaryjoin="foreign(AIStyleDimension.style_id) == AIStyle.id",
    )

    dimension: Mapped["AIDimension"] = relationship(
        "AIDimension",
        back_populates="style_dimensions",
        primaryjoin="foreign(AIStyleDimension.dimension_id) == AIDimension.id",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("style_id", "dimension_id", name="ai_style_dimensions_style_id_dimension_id_key"),
        CheckConstraint(
            "initial_position >= 0 AND initial_position <= 1000", name="ai_style_dimensions_position_range"
        ),
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

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="Status: 1=active, 2=inactive"
    )

    wake_time_min_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3000,
        server_default=text("3000"),
        comment="Minimum wake wait time (ms), minimum 500ms",
    )

    wake_time_max_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3000,
        server_default=text("3000"),
        comment="Maximum wake wait time (ms), must be >= min",
    )

    wake_time_bias: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="balanced",
        server_default=text("'balanced'"),
        comment="Sampling bias for wake time distribution",
    )

    wake_window_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60000,
        server_default=text("60000"),
        comment="Skip wake if last message within this window (ms)",
    )

    wake_time_adjustment: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="random_half",
        server_default=text("'random_half'"),
        comment="Wait time adjustment when new message arrives",
    )

    no_reply_probability: Mapped[float] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Probability of intentionally skipping a reply after wake",
    )

    followup_delay_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5000,
        server_default=text("5000"),
        comment="Delay between outgoing and followup messages in milliseconds",
    )

    # Relationships
    relationship_mappings: Mapped[List["AIDimensionRelationshipMapping"]] = relationship(
        "AIDimensionRelationshipMapping",
        back_populates="relationship",
        primaryjoin="AIRelationship.id == foreign(AIDimensionRelationshipMapping.relationship_id)",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("wake_time_min_ms >= 500", name="ck_ai_relationships_response_time_min"),
        CheckConstraint(
            "wake_time_max_ms >= wake_time_min_ms",
            name="ck_ai_relationships_response_time_bounds",
        ),
        CheckConstraint(
            "no_reply_probability >= 0 AND no_reply_probability <= 1",
            name="ck_ai_relationships_no_reply_probability",
        ),
    )

    def __admin_select2_repr__(self, request) -> str:
        from markupsafe import escape
        return f"<span>[{self.id}] {escape(self.display_name)}</span>"


class AIDimensionRelationshipMapping(AutoIncrementModel):
    """
    AI dimension relationship mapping model.

    Mapping from dimension position ranges to relationship types.
    """

    __tablename__ = "ai_dimension_relationship_mappings"

    dimension_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Dimension ID, references ai_dimensions.id",
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
        Integer, nullable=False, default=1, server_default=text("1"), comment="Priority level (default: 1)"
    )

    limit_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Maximum occurrence count, NULL means unlimited"
    )

    # Relationships
    dimension: Mapped["AIDimension"] = relationship(
        "AIDimension",
        back_populates="relationship_mappings",
        primaryjoin="foreign(AIDimensionRelationshipMapping.dimension_id) == AIDimension.id",
    )

    relationship: Mapped["AIRelationship"] = relationship(
        "AIRelationship",
        back_populates="relationship_mappings",
        primaryjoin="foreign(AIDimensionRelationshipMapping.relationship_id) == AIRelationship.id",
    )
