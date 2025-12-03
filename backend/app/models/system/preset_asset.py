from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel

if TYPE_CHECKING:
    from app.models.message import MediaFile


class PresetAsset(AutoIncrementModel):
    """Preset asset model for managing preset resources (avatars, emoticons, etc.)"""

    __tablename__ = "preset_assets"

    # Asset type: 1=avatar, 2=emoticon
    asset_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Asset type: 1=avatar, 2=emoticon"
    )

    # Asset name (unique identifier)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="Asset name")

    # Category (integer enum)
    category: Mapped[int] = mapped_column(Integer, nullable=False, comment="Category")

    # Is client preset (bundled with client)
    is_client_preset: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="Is client preset"
    )

    # Media file ID (references media_files table)
    file_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Media file ID, references media_files.id",
    )

    # URL for the asset
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="Asset URL")

    # Prompt for AI generation
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Generation prompt")

    # Description
    description: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Description"
    )

    # Status
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    # Sort order
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Sort order"
    )

    # Relationship to media_files
    media_file: Mapped[Optional["MediaFile"]] = relationship(
        "MediaFile",
        primaryjoin="foreign(PresetAsset.file_id) == MediaFile.id",
        lazy="select",
        viewonly=True,
    )

    # Indexes - Only essential indexes for MVP
    __table_args__ = (
        Index("idx_preset_assets_asset_type", "asset_type"),
        Index("idx_preset_assets_category", "category"),
        Index("idx_preset_assets_status", "status"),
        Index("idx_preset_assets_sort_order", "sort_order"),
    )
