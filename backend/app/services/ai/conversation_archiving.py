"""Conversation items archive maintenance service."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.services.system_config import get_config_bool, get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ARCHIVE_LOCK_KEY = 913_260_002

_KEY_ENABLED = "ai_conversation_archive_enabled"
_KEY_RETENTION_DAYS = "ai_conversation_archive_retention_days"
_KEY_KEEP_RECENT_COUNT = "ai_conversation_archive_keep_recent_count"
_KEY_BATCH_SIZE = "ai_conversation_archive_batch_size"

_DEFAULT_MAX_ROUNDS = 20
_MAX_ROUNDS_ENV_KEY = "AILO_CONVERSATION_ARCHIVE_MAX_ROUNDS"

_ARCHIVE_SQL = text(
    """
WITH ranked AS (
    SELECT
        i.id,
        i.user_qiao_id,
        i.instance_qiao_id,
        i.created_at,
        ROW_NUMBER() OVER (
            PARTITION BY i.user_qiao_id, i.instance_qiao_id
            ORDER BY i.created_at DESC, i.id DESC
        ) AS rn
    FROM ai_conversation_items AS i
),
candidates AS (
    SELECT
        r.id,
        r.user_qiao_id,
        r.instance_qiao_id,
        r.created_at
    FROM ranked AS r
    WHERE
        (
            r.created_at < (NOW() - (:retention_days * INTERVAL '1 day'))
            OR r.rn > :keep_recent_count
        )
        AND r.rn > :keep_recent_count
    ORDER BY r.created_at ASC, r.id ASC
    LIMIT :batch_size
),
inserted AS (
    INSERT INTO ai_conversation_items_archive (
        id,
        user_qiao_id,
        instance_qiao_id,
        role,
        message_type,
        text_content,
        media_url,
        media_metadata,
        client_msg_ids,
        buffer_id,
        is_excluded_from_context,
        created_at,
        archived_at
    )
    SELECT
        i.id,
        i.user_qiao_id,
        i.instance_qiao_id,
        i.role,
        i.message_type,
        i.text_content,
        i.media_url,
        i.media_metadata,
        i.client_msg_ids,
        i.buffer_id,
        i.is_excluded_from_context,
        i.created_at,
        NOW()
    FROM ai_conversation_items AS i
    INNER JOIN candidates AS c
        ON c.id = i.id
    ON CONFLICT (id) DO NOTHING
    RETURNING id
),
deleted AS (
    DELETE FROM ai_conversation_items AS i
    USING candidates AS c
    WHERE i.id = c.id
    RETURNING i.id
)
SELECT
    (SELECT COUNT(*) FROM candidates) AS candidates_count,
    (SELECT COUNT(*) FROM inserted) AS archived_count,
    (SELECT COUNT(*) FROM deleted) AS deleted_count,
    (
        SELECT COUNT(DISTINCT (c.user_qiao_id, c.instance_qiao_id))
        FROM candidates AS c
    ) AS scan_sessions_count
"""
)


@dataclass(frozen=True)
class ArchiveConfig:
    """Archive policy loaded from system_configs."""

    enabled: bool
    retention_days: int
    keep_recent_count: int
    batch_size: int


@dataclass(frozen=True)
class ArchiveRoundStats:
    """Metrics from one archive round."""

    candidates_count: int
    archived_count: int
    deleted_count: int
    scan_sessions_count: int


@dataclass(frozen=True)
class ArchiveJobStats:
    """Aggregated metrics from one archive job."""

    rounds: int
    candidates_count: int
    archived_count: int
    deleted_count: int
    scan_sessions_count: int
    duration_ms: int
    last_success_at: str


def _get_max_rounds() -> int:
    raw = os.getenv(_MAX_ROUNDS_ENV_KEY, str(_DEFAULT_MAX_ROUNDS)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable '{_MAX_ROUNDS_ENV_KEY}' must be integer") from exc
    if value < 1:
        raise ValueError(f"Environment variable '{_MAX_ROUNDS_ENV_KEY}' must be >= 1")
    return value


async def _load_archive_config(db: AsyncSession) -> ArchiveConfig:
    enabled = await get_config_bool(db, _KEY_ENABLED, required=True)
    retention_days = await get_config_int(db, _KEY_RETENTION_DAYS, required=True)
    keep_recent_count = await get_config_int(db, _KEY_KEEP_RECENT_COUNT, required=True)
    batch_size = await get_config_int(db, _KEY_BATCH_SIZE, required=True)

    if retention_days < 1:
        raise ValueError(f"Configuration '{_KEY_RETENTION_DAYS}' must be >= 1")
    if keep_recent_count < 0:
        raise ValueError(f"Configuration '{_KEY_KEEP_RECENT_COUNT}' must be >= 0")
    if batch_size < 1:
        raise ValueError(f"Configuration '{_KEY_BATCH_SIZE}' must be >= 1")

    return ArchiveConfig(
        enabled=enabled,
        retention_days=retention_days,
        keep_recent_count=keep_recent_count,
        batch_size=batch_size,
    )


async def _run_archive_round(db: AsyncSession, config: ArchiveConfig) -> ArchiveRoundStats:
    result = await db.execute(
        _ARCHIVE_SQL,
        {
            "retention_days": config.retention_days,
            "keep_recent_count": config.keep_recent_count,
            "batch_size": config.batch_size,
        },
    )
    row = result.one_or_none()
    if row is None:
        return ArchiveRoundStats(0, 0, 0, 0)

    return ArchiveRoundStats(
        candidates_count=int(row.candidates_count or 0),
        archived_count=int(row.archived_count or 0),
        deleted_count=int(row.deleted_count or 0),
        scan_sessions_count=int(row.scan_sessions_count or 0),
    )


async def _try_acquire_job_lock(db: AsyncSession) -> bool:
    result = await db.execute(select(func.pg_try_advisory_lock(_ARCHIVE_LOCK_KEY)))
    return bool(result.scalar() or False)


async def _release_job_lock(db: AsyncSession) -> None:
    await db.execute(select(func.pg_advisory_unlock(_ARCHIVE_LOCK_KEY)))


async def run_conversation_archive_job() -> ArchiveJobStats | None:
    """
    Execute conversation items archive job once.

    Returns:
        ArchiveJobStats when the job runs.
        None when lock is occupied or archive is disabled.
    """
    max_rounds = _get_max_rounds()
    started = time.monotonic()

    session_factory = get_sessionmaker()
    async with session_factory() as db:
        acquired = await _try_acquire_job_lock(db)
        await db.commit()
        if not acquired:
            logger.info("conversation_archive_lock_busy")
            return None

        try:
            config = await _load_archive_config(db)
            if not config.enabled:
                logger.info("conversation_archive_disabled")
                await db.commit()
                return None

            rounds = 0
            total_candidates = 0
            total_archived = 0
            total_deleted = 0
            total_sessions = 0

            for round_index in range(1, max_rounds + 1):
                round_stats = await _run_archive_round(db, config)
                await db.commit()

                rounds = round_index
                total_candidates += round_stats.candidates_count
                total_archived += round_stats.archived_count
                total_deleted += round_stats.deleted_count
                total_sessions += round_stats.scan_sessions_count

                if round_stats.candidates_count == 0:
                    break

            return ArchiveJobStats(
                rounds=rounds,
                candidates_count=total_candidates,
                archived_count=total_archived,
                deleted_count=total_deleted,
                scan_sessions_count=total_sessions,
                duration_ms=int((time.monotonic() - started) * 1000),
                last_success_at=datetime.now(UTC).isoformat(),
            )
        finally:
            try:
                await _release_job_lock(db)
                await db.commit()
            except Exception:  # pragma: no cover - best effort unlock logging
                logger.error("conversation_archive_unlock_failed", exc_info=True)
