"""
Media file related models.

This module contains SQLAlchemy models for media file management.
"""

from datetime import datetime

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

from app.models.base import SnowflakeModel


class MediaFile(SnowflakeModel):
    """
    Media file model.

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
    cdn_domain: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="CDN domain override"
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

    __table_args__ = (
        CheckConstraint(
            "storage_provider IN ('local', 'tencent_cos')",
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
