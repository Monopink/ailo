"""
Media file related models.

This module contains SQLAlchemy models for media file management.
"""

from typing import Optional
from sqlalchemy import BigInteger, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from enums import FileType, FileStatus, UploaderType
from models.base import SnowflakeQiaoModel


class MediaFile(SnowflakeQiaoModel):
    """
    Media file model.

    Media file storage and metadata management.
    """

    __tablename__ = "media_files"

    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="File storage path")

    file_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="File access URL")

    file_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="File type: 1=image, 2=audio, 3=video, 4=document"
    )

    original_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Original filename"
    )

    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="MIME type")

    file_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="File size in bytes")

    upload_by_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Uploader type: 1=user, 2=ai_character, 3=system"
    )

    upload_by_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Uploader internal ID")

    upload_by_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Uploader external ID"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="File status: 1=active, 2=processing, 3=failed, 0=deleted",
    )

    # Indexes
    __table_args__ = (
        Index("idx_media_files_file_type", "file_type"),
        Index("idx_media_files_upload_by_type", "upload_by_type"),
        Index("idx_media_files_upload_by_id", "upload_by_id"),
        Index("idx_media_files_upload_by_qiao_id", "upload_by_qiao_id"),
        Index("idx_media_files_status", "status"),
        Index("idx_media_files_created_at", "created_at"),
    )
