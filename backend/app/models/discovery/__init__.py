"""
Discovery (Square) models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.base import AutoIncrementModel
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from models.ai.template import AIType


class SquareTypeEntry(AutoIncrementModel):
    """Square exposure entry mapping categories to AI types."""

    __tablename__ = "square_type_entries"

    square_category: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Square discovery category (1=friend, 2=love, 3=talk, 4=bestie, 5=hobby)",
    )
    type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_types.id", ondelete="RESTRICT"),
        nullable=False,
        comment="AI type exposed in this slot",
    )
    exposure_strategy: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Exposure strategy (1=random, others reserved)",
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="1=active, 2=inactive",
    )
    ai_type: Mapped["AIType"] = relationship(
        "AIType",
        primaryjoin="AIType.id == SquareTypeEntry.type_id",
        viewonly=True,
    )
