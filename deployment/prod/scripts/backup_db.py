#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import gzip
import hashlib
import logging
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import SysLogHandler
from pathlib import Path
from urllib.parse import urlparse

try:
    import boto3
    from botocore.config import Config
except Exception:  # pragma: no cover
    boto3 = None
    Config = None

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

LOG_VALUE_MAX_LENGTH = 500


@dataclass(frozen=True)
class Settings:
    """Backup settings loaded from environment variables."""

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: int
    cos_secret_id: str
    cos_secret_key: str
    cos_region: str
    cos_bucket: str
    cos_endpoint: str
    backup_dir: Path
    lock_file: Path
    local_retention_days: int


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
        cos_secret_id=_getenv_required("TENCENT_COS_BACKUP_SECRET_ID"),
        cos_secret_key=_getenv_required("TENCENT_COS_BACKUP_SECRET_KEY"),
        cos_region=_getenv_required("TENCENT_COS_BACKUP_REGION"),
        cos_bucket=_getenv_required("TENCENT_COS_BACKUP_BUCKET"),
        cos_endpoint=_getenv_required("TENCENT_COS_BACKUP_ENDPOINT").rstrip("/"),
        backup_dir=Path(os.getenv("AILO_BACKUP_DIR", "/opt/ailo-prod/backups/database")),
        lock_file=Path(os.getenv("AILO_DB_BACKUP_LOCK_FILE", "/run/lock/ailo-db-backup.lock")),
        local_retention_days=int(os.getenv("AILO_DB_BACKUP_LOCAL_RETENTION_DAYS", "7")),
    )


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("ailo.db_backup")
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
                return s if len(s) <= LOG_VALUE_MAX_LENGTH else (s[:LOG_VALUE_MAX_LENGTH] + "...")

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


def _acquire_lock(lock_file: Path) -> tuple[int, object]:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    lock_handle = os.fdopen(fd, "r+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_handle.close()
        raise
    lock_handle.seek(0)
    lock_handle.truncate(0)
    lock_handle.write(f"pid={os.getpid()} started_at={datetime.now(UTC).isoformat()}\n")
    lock_handle.flush()
    return fd, lock_handle


def _release_lock(lock_handle: object) -> None:
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
    finally:
        with suppress(Exception):
            lock_handle.close()  # type: ignore[attr-defined]


def _run_pg_dump(*, settings: Settings, output_path: Path, logger: logging.Logger) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={settings.postgres_password}",
        "-u",
        "postgres",
        "postgres",
        "pg_dump",
        "--no-owner",
        "--no-acl",
        "--format=plain",
        "--username",
        settings.postgres_user,
        "--dbname",
        settings.postgres_db,
    ]
    cmd_for_log = ["PGPASSWORD=***" if item.startswith("PGPASSWORD=") else item for item in cmd]
    logger.info("pg_dump_start", extra={"cmd": " ".join(cmd_for_log), "output_path": str(output_path)})
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    stderr_chunks: list[bytes] = []

    def _read_stderr() -> None:
        try:
            while True:
                chunk = proc.stderr.read(8192)
                if not chunk:
                    break
                if sum(len(c) for c in stderr_chunks) < 256 * 1024:
                    stderr_chunks.append(chunk)
        except Exception:
            return

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    with gzip.open(output_path, "wb") as gz:
        while True:
            chunk = proc.stdout.read(1024 * 1024)
            if not chunk:
                break
            gz.write(chunk)

    rc = proc.wait()
    stderr_thread.join(timeout=2)
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
    if rc != 0:
        raise RuntimeError(f"pg_dump_failed rc={rc} stderr={stderr}")

    if stderr:
        logger.info("pg_dump_stderr", extra={"stderr": stderr})


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _cos_client(settings: Settings) -> object:
    if boto3 is None or Config is None:
        raise RuntimeError("Missing required python package: boto3")
    cfg = Config(s3={"addressing_style": "virtual"})
    return boto3.client(
        "s3",
        aws_access_key_id=settings.cos_secret_id,
        aws_secret_access_key=settings.cos_secret_key,
        region_name=settings.cos_region,
        endpoint_url=settings.cos_endpoint,
        config=cfg,
    )


def _db_connect(settings: Settings) -> object:
    if psycopg2 is None:
        raise RuntimeError("Missing required python package: psycopg2-binary")
    return psycopg2.connect(
        host="127.0.0.1",
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
        connect_timeout=5,
    )


def _db_insert_running(
    *,
    settings: Settings,
    started_at: datetime,
    logger: logging.Logger,
) -> int | None:
    try:
        conn = _db_connect(settings)
    except Exception as exc:
        logger.error("db_connect_failed", extra={"error": str(exc)})
        return None

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO backup_jobs (status, started_at) VALUES (%s, %s) RETURNING id;",
                (1, started_at),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("insert_failed_no_id")
            return int(row[0])
    finally:
        conn.close()


def _db_update_success(
    *,
    settings: Settings,
    job_id: int,
    finished_at: datetime,
    duration_ms: int,
    backup_file_name: str,
    object_key: str,
    bucket_name: str,
    storage_region: str,
    file_size: int,
    sha256: str,
    etag: str | None,
) -> None:
    try:
        conn = _db_connect(settings)
    except Exception as exc:
        raise RuntimeError(f"backup_job_success_update_connect_failed: {exc}") from exc

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
UPDATE backup_jobs SET
  status = %s,
  finished_at = %s,
  duration_ms = %s,
  backup_file_name = %s,
  object_key = %s,
  bucket_name = %s,
  storage_region = %s,
  file_size = %s,
  sha256 = %s,
  etag = %s,
  error_message = %s
WHERE id = %s;
""".strip(),
                (
                    2,
                    finished_at,
                    duration_ms,
                    backup_file_name,
                    object_key,
                    bucket_name,
                    storage_region,
                    file_size,
                    sha256,
                    etag,
                    None,
                    job_id,
                ),
            )
    finally:
        conn.close()


def _db_insert_terminal(
    *,
    settings: Settings,
    status: int,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: int,
    backup_file_name: str | None,
    object_key: str | None,
    bucket_name: str | None,
    storage_region: str | None,
    file_size: int | None,
    sha256: str | None,
    etag: str | None,
    error_message: str | None,
    logger: logging.Logger,
) -> None:
    try:
        conn = _db_connect(settings)
    except Exception as exc:
        logger.error("db_connect_failed", extra={"error": str(exc)})
        return

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
INSERT INTO backup_jobs (
  status, started_at, finished_at, duration_ms,
  backup_file_name, object_key, bucket_name, storage_region,
  file_size, sha256, etag, error_message
) VALUES (
  %s, %s, %s, %s,
  %s, %s, %s, %s,
  %s, %s, %s, %s
);
""".strip(),
                (
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    backup_file_name,
                    object_key,
                    bucket_name,
                    storage_region,
                    file_size,
                    sha256,
                    etag,
                    error_message,
                ),
            )
    finally:
        conn.close()


def _cleanup_local_files(*, backup_dir: Path, retention_days: int, logger: logging.Logger) -> None:
    cutoff = time.time() - (retention_days * 24 * 60 * 60)
    deleted = 0
    for path in backup_dir.glob("db-*.sql.gz"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except Exception as exc:
            logger.error("local_cleanup_failed", extra={"path": str(path), "error": str(exc)})
    logger.info("local_cleanup_done", extra={"deleted": deleted, "retention_days": retention_days})


def main() -> int:
    """Run one database backup cycle and write the job record into backup_jobs."""
    logger = _setup_logging()
    try:
        settings = _load_settings()
    except Exception as exc:
        logger.error("settings_invalid", extra={"error": str(exc)})
        return 2

    started_at = datetime.now(UTC)
    job_id = None
    lock_handle = None

    try:
        _, lock_handle = _acquire_lock(settings.lock_file)
    except OSError:
        logger.error("backup_in_progress")
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        _db_insert_terminal(
            settings=settings,
            status=3,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            backup_file_name=None,
            object_key=None,
            bucket_name=settings.cos_bucket,
            storage_region=settings.cos_region,
            file_size=None,
            sha256=None,
            etag=None,
            error_message="backup_in_progress",
            logger=logger,
        )
        return 1

    try:
        job_id = _db_insert_running(settings=settings, started_at=started_at, logger=logger)

        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup_file_name = f"db-{ts}.sql.gz"
        backup_path = settings.backup_dir / backup_file_name

        _run_pg_dump(settings=settings, output_path=backup_path, logger=logger)

        sha256 = _sha256_file(backup_path)
        file_size = backup_path.stat().st_size

        now_utc = datetime.now(UTC)
        object_key = f"db-backups/{now_utc:%Y}/{now_utc:%m}/{backup_file_name}"
        sha_key = f"{object_key}.sha256"

        parsed = urlparse(settings.cos_endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError("cos_endpoint_invalid")
        if (parsed.hostname or "").startswith(f"{settings.cos_bucket}."):
            raise RuntimeError("cos_endpoint_must_be_service_domain")

        client = _cos_client(settings)
        client.upload_file(
            str(backup_path),
            settings.cos_bucket,
            object_key,
            ExtraArgs={"ContentType": "application/gzip", "ServerSideEncryption": "AES256"},
        )
        client.put_object(
            Bucket=settings.cos_bucket,
            Key=sha_key,
            Body=(sha256 + "\n").encode("utf-8"),
            ContentType="text/plain",
            ServerSideEncryption="AES256",
        )

        head = client.head_object(Bucket=settings.cos_bucket, Key=object_key)
        remote_size = int(head.get("ContentLength") or 0)
        if remote_size != file_size:
            raise RuntimeError(f"cos_size_mismatch local={file_size} remote={remote_size}")

        sse = head.get("ServerSideEncryption")
        if sse is None:
            logger.info("cos_encryption_unknown")
        elif sse != "AES256":
            raise RuntimeError(f"cos_encryption_mismatch expected=AES256 got={sse}")

        etag = (head.get("ETag") or "").strip('"') or None

        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        if job_id is not None:
            _db_update_success(
                settings=settings,
                job_id=job_id,
                finished_at=finished_at,
                duration_ms=duration_ms,
                backup_file_name=backup_file_name,
                object_key=object_key,
                bucket_name=settings.cos_bucket,
                storage_region=settings.cos_region,
                file_size=file_size,
                sha256=sha256,
                etag=etag,
            )
        else:
            _db_insert_terminal(
                settings=settings,
                status=2,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                backup_file_name=backup_file_name,
                object_key=object_key,
                bucket_name=settings.cos_bucket,
                storage_region=settings.cos_region,
                file_size=file_size,
                sha256=sha256,
                etag=etag,
                error_message=None,
                logger=logger,
            )

        _cleanup_local_files(
            backup_dir=settings.backup_dir,
            retention_days=settings.local_retention_days,
            logger=logger,
        )
        logger.info("backup_success", extra={"object_key": object_key, "sha256": sha256})
        return 0
    except Exception as exc:
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        error_message = str(exc)[:2000]
        if job_id is not None:
            conn = None
            try:
                conn = _db_connect(settings)
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        """
UPDATE backup_jobs SET
  status = %s,
  finished_at = %s,
  duration_ms = %s,
  error_message = %s
WHERE id = %s;
""".strip(),
                        (3, finished_at, duration_ms, error_message, job_id),
                    )
            except Exception as db_exc:
                logger.error("db_update_failed", extra={"error": str(db_exc), "job_id": job_id})
            finally:
                try:
                    if conn is not None:
                        conn.close()
                except Exception as close_exc:
                    logger.error(
                        "db_close_failed",
                        extra={"error": str(close_exc), "job_id": job_id},
                    )
        else:
            _db_insert_terminal(
                settings=settings,
                status=3,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                backup_file_name=None,
                object_key=None,
                bucket_name=settings.cos_bucket,
                storage_region=settings.cos_region,
                file_size=None,
                sha256=None,
                etag=None,
                error_message=error_message,
                logger=logger,
            )
        logger.error("backup_failed", extra={"error": error_message})
        return 1
    finally:
        if lock_handle is not None:
            _release_lock(lock_handle)


if __name__ == "__main__":
    raise SystemExit(main())
