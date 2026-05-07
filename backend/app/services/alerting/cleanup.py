"""
Alerting cleanup worker.

Deletes old rows from alert_events and alert_event_entities based on retention days.
This worker is best-effort and must not block application startup.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.database import get_sessionmaker
from app.crud.system.alerting import alert_events
from app.exceptions import ConfigurationError, MissingConfigurationError
from app.services.system_config import get_config_bool, get_config_int
from app.utils.logging import get_logger

logger = get_logger(__name__)

_ALERTING_CLEANUP_LOCK_KEY = 913_260_001

_KEY_ENABLED = "alerting_cleanup_enabled"
_KEY_INTERVAL_SECONDS = "alerting_cleanup_interval_seconds"
_KEY_RETENTION_DAYS = "alerting_default_retention_days"
_KEY_RETENTION_DAYS_DEBUG = "alerting_retention_days_debug"
_KEY_RETENTION_DAYS_INFO = "alerting_retention_days_info"
_KEY_RETENTION_DAYS_WARNING = "alerting_retention_days_warning"
_KEY_RETENTION_DAYS_ERROR = "alerting_retention_days_error"
_KEY_RETENTION_DAYS_CRITICAL = "alerting_retention_days_critical"


def _validate_retention(*, key: str, value: int) -> int:
    if value < 0:
        raise ConfigurationError(
            message=f"Configuration '{key}' must be >= 0.",
            config_key=key,
            details={"value": value},
        )
    return value


async def _try_run_cleanup_once() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        enabled = await get_config_bool(db, _KEY_ENABLED, required=True)
        default_retention_days = _validate_retention(
            key=_KEY_RETENTION_DAYS,
            value=await get_config_int(db, _KEY_RETENTION_DAYS, required=True),
        )
        retention_days_by_severity = {
            10: _validate_retention(
                key=_KEY_RETENTION_DAYS_DEBUG,
                value=await get_config_int(db, _KEY_RETENTION_DAYS_DEBUG, required=True),
            ),
            20: _validate_retention(
                key=_KEY_RETENTION_DAYS_INFO,
                value=await get_config_int(db, _KEY_RETENTION_DAYS_INFO, required=True),
            ),
            30: _validate_retention(
                key=_KEY_RETENTION_DAYS_WARNING,
                value=await get_config_int(db, _KEY_RETENTION_DAYS_WARNING, required=True),
            ),
            40: _validate_retention(
                key=_KEY_RETENTION_DAYS_ERROR,
                value=await get_config_int(db, _KEY_RETENTION_DAYS_ERROR, required=True),
            ),
            50: _validate_retention(
                key=_KEY_RETENTION_DAYS_CRITICAL,
                value=await get_config_int(db, _KEY_RETENTION_DAYS_CRITICAL, required=True),
            ),
        }

        if not enabled:
            logger.info("alerting_cleanup_disabled")
            return

        if default_retention_days <= 0 and not any(
            v > 0 for v in retention_days_by_severity.values()
        ):
            return

        acquired = bool(
            (
                await db.execute(select(func.pg_try_advisory_lock(_ALERTING_CLEANUP_LOCK_KEY)))
            ).scalar()
            or False
        )
        if not acquired:
            logger.info("alerting_cleanup_lock_busy")
            return

        try:
            deleted = await alert_events.cleanup_old_by_severity(
                db,
                retention_days_by_severity=retention_days_by_severity,
                default_retention_days=default_retention_days,
            )
            await db.commit()
            logger.info(
                "alerting_cleanup_completed",
                deleted=deleted,
                default_retention_days=default_retention_days,
                retention_days_by_severity=retention_days_by_severity,
            )
        finally:
            try:
                await db.execute(select(func.pg_advisory_unlock(_ALERTING_CLEANUP_LOCK_KEY)))
            except Exception:  # pragma: no cover - best effort unlock logging
                logger.error("alerting_cleanup_unlock_failed", exc_info=True)


async def _alerting_cleanup_loop() -> None:
    while True:
        try:
            await _try_run_cleanup_once()
        except (MissingConfigurationError, ConfigurationError):
            logger.error("alerting_cleanup_config_error", exc_info=True)
        except Exception:  # pragma: no cover - best effort loop logging
            logger.error("alerting_cleanup_loop_error", exc_info=True)

        try:
            session_factory = get_sessionmaker()
            async with session_factory() as db:
                interval_seconds = await get_config_int(db, _KEY_INTERVAL_SECONDS, required=True)
                if interval_seconds < 1:
                    raise ConfigurationError(
                        message=f"Configuration '{_KEY_INTERVAL_SECONDS}' must be >= 1.",
                        config_key=_KEY_INTERVAL_SECONDS,
                        details={"value": interval_seconds},
                    )
        except (MissingConfigurationError, ConfigurationError):
            logger.error("alerting_cleanup_interval_config_error", exc_info=True)
            interval_seconds = 60
        except Exception:
            logger.error("alerting_cleanup_interval_read_failed", exc_info=True)
            interval_seconds = 60

        await asyncio.sleep(max(int(interval_seconds), 1))


def start_alerting_cleanup_worker(app: FastAPI) -> None:
    """Start background cleanup worker for alerting."""
    task = asyncio.create_task(_alerting_cleanup_loop())
    app.state.alerting_cleanup_task = task
    logger.info("alerting_cleanup_worker_started")


async def stop_alerting_cleanup_worker(app: FastAPI) -> None:
    """Stop background cleanup worker for alerting."""
    task: asyncio.Task[None] | None = getattr(app.state, "alerting_cleanup_task", None)
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
        pass
    logger.info("alerting_cleanup_worker_stopped")
