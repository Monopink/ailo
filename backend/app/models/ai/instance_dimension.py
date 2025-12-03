"""
AI instance dimension related models.

This module contains SQLAlchemy models for AI instance dimension scores.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SnowflakeModel

if TYPE_CHECKING:
    from app.models.ai.instance import AIInstance
    from app.models.ai.style import AIDimension


class AIInstanceDimension(SnowflakeModel):
    """
    AI instance dimension score model.

    Dimension scoring for each instance.
    """

    __tablename__ = "ai_instance_dimensions"

    instance_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Instance ID, references ai_instances.id"
    )

    dimension_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Dimension ID, references ai_dimensions.id"
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="Current score value")

    position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Per mille position (0-1000)"
    )

    position_mapping_algorithm: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        server_default=text("1"),
        comment="Position mapping algorithm: 1=direct, 2=V1",
    )

    position_mapping_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Position mapping parameters (JSONB)",
    )

    # Relationships
    instance: Mapped["AIInstance"] = relationship(
        "AIInstance",
        primaryjoin="AIInstanceDimension.instance_id == AIInstance.id",
        foreign_keys=[instance_id],
        lazy="select",
        viewonly=True,
    )
    dimension: Mapped["AIDimension"] = relationship(
        "AIDimension",
        primaryjoin="AIInstanceDimension.dimension_id == AIDimension.id",
        foreign_keys=[dimension_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes and constraints - Only essential indexes for MVP
    __table_args__ = (
        UniqueConstraint(
            "instance_id",
            "dimension_id",
            name="ai_instance_dimensions_instance_id_dimension_id_key",
        ),
        Index("idx_ai_instance_dimensions_instance_id", "instance_id"),
        Index("idx_ai_instance_dimensions_dimension_id", "dimension_id"),
    )
