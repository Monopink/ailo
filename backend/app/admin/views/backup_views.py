"""Backup related admin views.

This module contains Starlette-Admin views for monitoring database backup jobs.
All views are read-only.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette_admin import DateTimeField, IntegerField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView

from app.admin.views.base import IntegerEnumField
from app.enums import BackupJobStatus
from app.models.backup import BackupJob


class BackupJobView(ModelView):
    """Backup jobs view for monitoring."""

    label = "Backup Jobs"
    name = "Backup Jobs"

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    fields_default_sort = [("started_at", True)]
    searchable_fields = [
        "id",
        "backup_file_name",
        "object_key",
        "sha256",
        "etag",
        "error_message",
    ]
    sortable_fields = [
        "id",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "file_size",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Auto-increment ID"),
        IntegerEnumField(
            "status",
            enum=BackupJobStatus,
            label="Status",
            help_text="Backup job status",
        ),
        DateTimeField("started_at", label="Started At", help_text="Backup start time"),
        DateTimeField(
            "finished_at",
            label="Finished At",
            help_text="Backup finish time",
            required=False,
        ),
        IntegerField(
            "duration_ms",
            label="Duration (ms)",
            help_text="Backup duration in milliseconds",
            required=False,
        ),
        StringField(
            "backup_file_name",
            label="Backup File",
            help_text="Backup file name (db-YYYYMMDD-HHMMSS.sql.gz)",
            required=False,
        ),
        StringField(
            "object_key",
            label="Object Key",
            help_text="COS object key for main backup file",
            required=False,
        ),
        StringField(
            "bucket_name",
            label="Bucket",
            help_text="COS bucket name",
            required=False,
        ),
        StringField(
            "storage_region",
            label="Region",
            help_text="COS region",
            required=False,
        ),
        IntegerField(
            "file_size",
            label="Size (bytes)",
            help_text="Backup file size in bytes",
            required=False,
        ),
        StringField(
            "sha256",
            label="SHA-256",
            help_text="SHA-256 of main backup file",
            required=False,
        ),
        StringField(
            "etag",
            label="ETag",
            help_text="ETag for record only (not for integrity)",
            required=False,
        ),
        TextAreaField(
            "error_message",
            label="Error",
            help_text="Failure reason (if any)",
            required=False,
        ),
        DateTimeField("created_at", label="Created At", help_text="Record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Record update time"),
    ]


backup_job_view = BackupJobView(BackupJob, icon="fa fa-database")
