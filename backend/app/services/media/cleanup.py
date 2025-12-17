"""
Cleanup jobs for orphaned media files.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.enums import FileStatus
from app.models.message import MediaFile
from app.services.storage.base import StorageError
from app.services.storage.factory import get_storage_backend
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def cleanup_expired_pending_files(
    db: AsyncSession, *, older_than_minutes: int = 60, batch_size: int = 200
) -> int:
    """Delete pending media files that were never confirmed within TTL."""
    cutoff = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
    result = await db.execute(
        select(MediaFile)
        .where(MediaFile.status == int(FileStatus.PENDING))
        .where(MediaFile.created_at < cutoff)
        .limit(batch_size)
    )
    files = list(result.scalars().all())
    if not files:
        return 0

    storage = get_storage_backend()
    removed = 0
    for file in files:
        try:
            storage.delete(file.object_key)
        except StorageError:
            logger.warning("media_cleanup_storage_delete_failed", file_id=file.file_id)
        file.status = int(FileStatus.DELETED)
        db.add(file)
        removed += 1

    await db.commit()
    logger.info("media_cleanup_completed", removed=removed)
    return removed


async def _media_cleanup_loop(interval_seconds: int) -> None:
    session_factory = get_sessionmaker()
    while True:
        try:
            async with session_factory() as db:
                await cleanup_expired_pending_files(db)
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.error("media_cleanup_loop_error", error=str(exc), exc_info=True)
        await asyncio.sleep(interval_seconds)


def start_media_cleanup_worker(app: FastAPI, interval_minutes: int = 60) -> None:
    """Start background cleanup worker."""
    interval_seconds = max(interval_minutes, 1) * 60
    task = asyncio.create_task(_media_cleanup_loop(interval_seconds))
    app.state.media_cleanup_task = task
    logger.info("media_cleanup_worker_started", interval_minutes=interval_minutes)


async def stop_media_cleanup_worker(app: FastAPI) -> None:
    """Stop background cleanup worker."""
    task: asyncio.Task[None] | None = getattr(app.state, "media_cleanup_task", None)
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
        pass
    logger.info("media_cleanup_worker_stopped")
