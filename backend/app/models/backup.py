"""Backup related models.

This module contains SQLAlchemy models for backup job records written by host scripts.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AutoIncrementModel


class BackupJob(AutoIncrementModel):
    """Backup job execution record."""

    __tablename__ = "backup_jobs"

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Status: 1=running, 2=success, 3=failed",
    )

    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Job start time"
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Job finish time"
    )

    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Duration in milliseconds"
    )

    backup_file_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Backup file name (db-YYYYMMDD-HHMMSS.sql.gz)"
    )

    object_key: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="COS object key for main backup file"
    )

    bucket_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="COS bucket name"
    )

    storage_region: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="COS region"
    )

    file_size: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Backup file size in bytes"
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="SHA-256 of main backup file"
    )

    etag: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="ETag for record only (not for integrity)"
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Failure reason")
