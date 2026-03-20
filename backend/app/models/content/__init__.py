"""Content models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel

from .app_page import AppPage

if TYPE_CHECKING:
    from app.models.ai.template import AIType


class SquareCategory(AutoIncrementModel):
    """Square category definitions exposed to clients."""

    __tablename__ = "square_categories"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="Square category ID"
    )
    category_key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="Stable category key in kebab-case"
    )
    title: Mapped[str] = mapped_column(String(50), nullable=False, comment="Category display title")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Category description"
    )
    theme_key: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Theme key used by client"
    )
    icon_ref: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="TDesign icon reference: tdesign:<icon-name>"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default=text("100"),
        comment="Ascending sort priority",
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="1=active, 2=inactive"
    )
    square_entries: Mapped[list[SquareTypeEntry]] = relationship(
        "SquareTypeEntry",
        primaryjoin="SquareCategory.category_key == SquareTypeEntry.category_key",
        foreign_keys="SquareTypeEntry.category_key",
        viewonly=True,
    )


class SquareTypeEntry(AutoIncrementModel):
    """Square exposure entry mapping categories to AI types."""

    __tablename__ = "square_type_entries"

    category_key: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("square_categories.category_key", ondelete="RESTRICT"),
        nullable=False,
        comment="Square category key (references square_categories.category_key)",
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
    category: Mapped[SquareCategory] = relationship(
        "SquareCategory",
        primaryjoin="SquareTypeEntry.category_key == SquareCategory.category_key",
        foreign_keys=[category_key],
        viewonly=True,
    )
    ai_type: Mapped[AIType] = relationship(
        "AIType",
        primaryjoin="AIType.id == SquareTypeEntry.type_id",
        viewonly=True,
    )


__all__ = ["AppPage", "SquareCategory", "SquareTypeEntry"]
