"""Backup-related enums."""

from enum import IntEnum


class BackupJobStatus(IntEnum):
    """Backup job status (backup_jobs.status)."""

    RUNNING = 1
    SUCCESS = 2
    FAILED = 3
