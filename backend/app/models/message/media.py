"""Media file related models.

This module contains SQLAlchemy models for media file management.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from markupsafe import escape
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship
from starlette.requests import Request

from app.models.base import SnowflakeModel

if TYPE_CHECKING:
    from app.models.admin import AdminUser
    from app.models.user import User


class MediaFile(SnowflakeModel):
    """Media file model.

    Media file storage and metadata management.
    """

    __tablename__ = "media_files"

    file_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    file_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1=avatar,2=emoji,3=image,4=document"
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Optional secondary category"
    )
    storage_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Storage provider identifier"
    )
    bucket_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Bucket name for cloud storage"
    )
    object_key: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Object key within storage backend"
    )
    storage_region: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Storage region identifier"
    )
    original_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Original filename at upload time"
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="File size in bytes")
    mime_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Declared MIME type"
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="SHA-256 hash for deduplication"
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    upload_by_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Uploader type: 1=user,2=admin,3=system"
    )
    upload_by_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Uploader internal ID"
    )
    upload_by_qiao_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Uploader external qiao_id"
    )
    etag: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Storage provider returned ETag"
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Upload confirmation time"
    )
    confirmed_by_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Confirming operator ID"
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default=text("2"),
        comment="File status: 1=active,2=pending,3=deleted",
    )

    uploader_user: Mapped["User | None"] = orm_relationship(
        "User",
        primaryjoin="MediaFile.upload_by_id == User.id",
        foreign_keys="[MediaFile.upload_by_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )
    confirmed_by_admin: Mapped["AdminUser | None"] = orm_relationship(
        "AdminUser",
        primaryjoin="MediaFile.confirmed_by_id == AdminUser.id",
        foreign_keys="[MediaFile.confirmed_by_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    __table_args__ = (
        CheckConstraint(
            "storage_provider = 'tencent_cos'",
            name="ck_media_files_storage_provider",
        ),
        CheckConstraint(
            "status IN (1,2,3)",
            name="ck_media_files_status",
        ),
        CheckConstraint(
            "file_type IN (1,2,3,4)",
            name="ck_media_files_file_type",
        ),
        UniqueConstraint(
            "storage_provider",
            "bucket_name",
            "object_key",
            name="uq_media_files_storage_object",
        ),
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        """Display representation in admin select2 dropdown."""
        file_type_map = {1: "Avatar", 2: "Emoji", 3: "Image", 4: "Document"}
        file_type_str = file_type_map.get(self.file_type, "Unknown")
        # Show: [ID] file_type / original_name / object_key
        return (
            f"<span>[{self.id}] {file_type_str} / {escape(self.original_name)} / "
            f"{escape(self.object_key)}</span>"
        )
