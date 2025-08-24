"""
Emoticon related models.

This module contains SQLAlchemy models for emoticon management.
"""

from typing import Optional
from sqlalchemy import Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from enums import EmoticonCategory, EmoticonCreatorType
from models.base import AutoIncrementModel


class Emoticon(AutoIncrementModel):
    """
    Emoticon model.

    Emoticon and sticker management.
    """

    __tablename__ = "emoticons"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="Unique identifier")

    category: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Emoticon category: 1=emoji, 2=sticker, 3=custom"
    )

    file_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Media file ID, references media_files.qiao_id"
    )

    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Image URL")

    description: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Emoticon description"
    )

    created_by_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Creator type: 1=system, 2=user, 3=admin"
    )

    created_by_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Creator internal ID")

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 0=inactive"
    )

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Sort order")

    # Indexes
    __table_args__ = (
        Index("idx_emoticons_code", "code"),
        Index("idx_emoticons_category", "category"),
        Index("idx_emoticons_created_by_type", "created_by_type"),
        Index("idx_emoticons_created_by_id", "created_by_id"),
        Index("idx_emoticons_status", "status"),
        Index("idx_emoticons_sort_order", "sort_order"),
    )
