"""Content models."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from starlette.requests import Request

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
    minor_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Whether category is visible in minor mode",
    )
    review_visibility_scope: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment=(
            "Review visibility scope: 0=all users, 1=regular users, "
            "2=all reviewers, 3=mp_weixin reviewers"
        ),
    )
    square_entries: Mapped[list[SquareTypeEntry]] = relationship(
        "SquareTypeEntry",
        primaryjoin="SquareCategory.category_key == SquareTypeEntry.category_key",
        foreign_keys="SquareTypeEntry.category_key",
        viewonly=True,
    )
    __table_args__ = (
        CheckConstraint(
            "review_visibility_scope IN (0, 1, 2, 3)",
            name="ck_square_categories_review_visibility_scope",
        ),
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.title)} ({escape(self.category_key)})</span>"


class SquareTypeEntry(AutoIncrementModel):
    """Square exposure entry mapping categories to AI types (many-to-many)."""

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


class SquareUserCategoryState(AutoIncrementModel):
    """Per-user per-category square refresh state."""

    __tablename__ = "square_user_category_state"

    user_qiao_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Owner user qiao_id",
    )
    category_key: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("square_categories.category_key", ondelete="CASCADE"),
        nullable=False,
        comment="Square category key",
    )
    feed_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Current feed version for this user-category",
    )
    last_refreshed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Timestamp when feed version was last rotated",
    )
    next_refresh_available_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Next timestamp when feed rotation is allowed",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_qiao_id",
            "category_key",
            name="uq_square_user_category_state_user_category",
        ),
        Index(
            "idx_square_user_category_state_user_category",
            "user_qiao_id",
            "category_key",
        ),
        Index(
            "idx_square_user_category_state_next_refresh",
            "next_refresh_available_at",
        ),
    )


__all__ = ["AppPage", "SquareCategory", "SquareTypeEntry", "SquareUserCategoryState"]
