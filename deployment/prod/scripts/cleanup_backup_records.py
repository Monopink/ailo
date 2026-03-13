#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import SysLogHandler


@dataclass(frozen=True)
class Settings:
    """Cleanup settings loaded from environment variables."""

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: int
    retention_days: int


def _getenv_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


def _load_settings() -> Settings:
    return Settings(
        postgres_user=_getenv_required("POSTGRES_USER"),
        postgres_password=_getenv_required("POSTGRES_PASSWORD"),
        postgres_db=_getenv_required("POSTGRES_DB"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        retention_days=int(os.getenv("AILO_BACKUP_JOBS_RETENTION_DAYS", "90")),
    )


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("ailo.backup_jobs_cleanup")
    logger.setLevel(logging.INFO)

    base_attrs = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
    }

    class KVFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            extras = {
                k: v
                for k, v in record.__dict__.items()
                if k not in base_attrs and not k.startswith("_")
            }
            if not extras:
                record.kv = ""  # type: ignore[attr-defined]
                return True

            def _safe(v: object) -> str:
                s = str(v)
                s = s.replace("\n", "\\n")
                return s if len(s) <= 500 else (s[:500] + "...")

            kv = " " + " ".join(f"{k}={_safe(extras[k])}" for k in sorted(extras))
            record.kv = kv  # type: ignore[attr-defined]
            return True

    formatter = logging.Formatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s%(kv)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(KVFilter())
    logger.addHandler(stream_handler)

    try:
        syslog_handler = SysLogHandler(address="/dev/log")
        syslog_handler.setFormatter(logging.Formatter("%(name)s: %(levelname)s %(message)s%(kv)s"))
        syslog_handler.addFilter(KVFilter())
        logger.addHandler(syslog_handler)
    except Exception as exc:
        logger.info("syslog_unavailable", extra={"error": str(exc)})

    return logger


def _db_connect(settings: Settings):
    try:
        import psycopg2
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing required python package: psycopg2-binary") from exc

    return psycopg2.connect(
        host="127.0.0.1",
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
        connect_timeout=5,
    )


def main() -> int:
    """Delete old backup_jobs rows based on retention policy."""
    logger = _setup_logging()
    try:
        settings = _load_settings()
    except Exception as exc:
        logger.error("settings_invalid", extra={"error": str(exc)})
        return 2

    conn = None
    try:
        conn = _db_connect(settings)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM backup_jobs WHERE created_at < NOW() - (%s || ' days')::interval;",
                (settings.retention_days,),
            )
            deleted = cur.rowcount
        logger.info(
            "cleanup_done",
            extra={
                "deleted": deleted,
                "retention_days": settings.retention_days,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )
        return 0
    except Exception as exc:
        logger.error("cleanup_failed", extra={"error": str(exc)})
        return 1
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception as close_exc:
            logger.error("db_close_failed", extra={"error": str(close_exc)})


if __name__ == "__main__":
    raise SystemExit(main())
