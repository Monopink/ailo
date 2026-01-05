"""
Message and media-related model views for Starlette-Admin.
Creates ModelView instances for message system and media management.
"""

from collections.abc import MutableMapping, Sequence
from typing import Any, ClassVar, SupportsInt, cast

from starlette.requests import Request
from starlette_admin import BooleanField, IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField

from app.admin.fields import LocalDateTimeField
from app.admin.views.base import IntegerEnumField
from app.enums import (
    FileStatus,
    FileType,
    MessageDirection,
    MessageParticipantType,
    MessageStatus,
    MessageType,
    NotificationStatus,
    NotificationType,
    ServiceProvider,
    UploaderType,
)
from app.models.message import MessageDeliveryFailure
from app.models.message.media import MediaFile
from app.models.message.message import MessageHistory
from app.models.message.notification import NotificationPushHistory


def _coerce_int(value: object, field: str) -> int:
    """Convert arbitrary object to int or raise validation error."""
    if isinstance(value, SupportsInt):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise FormValidationError({field: "Invalid value"}) from exc
    raise FormValidationError({field: "Invalid value"})


class MessageHistoryView(ModelView):
    """Enhanced Message History view - read-only for monitoring."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    exclude_fields_from_list: ClassVar[list[str]] = []
    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = [
        "conversation_id",
        "from_qiao_id",
        "to_qiao_id",
    ]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "direction",
        "platform",
        "message_type",
        "status",
        "created_at",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            IntegerEnumField(
                "direction", enum=MessageDirection, label="Direction", help_text="Message direction"
            ),
            IntegerEnumField(
                "platform",
                choices=[(1, "iOS"), (2, "Android"), (3, "Web"), (4, "Mini Program")],
                label="Platform",
                help_text="Source platform",
            ),
            StringField(
                "conversation_id", label="Conversation ID", help_text="Conversation identifier"
            ),
            StringField(
                "msg_id_server", label="Server Message ID", help_text="Server-generated message ID"
            ),
            StringField(
                "msg_id_provider_inbound",
                label="Inbound Provider Message ID",
                help_text="Third-party provider message ID for inbound messages",
            ),
            StringField(
                "msg_id_provider_outbound",
                label="Outbound Provider Message ID",
                help_text="Third-party provider message ID for outbound messages",
            ),
            StringField(
                "msg_id_client", label="Client Message ID", help_text="Client-generated message ID"
            ),
            "client_sent_time",
            IntegerEnumField(
                "from_type", enum=MessageParticipantType, label="From Type", help_text="Sender type"
            ),
            StringField("from_id", label="From ID", help_text="Sender snowflake ID"),
            StringField("from_qiao_id", label="From Qiao ID", help_text="Sender external ID"),
            IntegerEnumField(
                "to_type", enum=MessageParticipantType, label="To Type", help_text="Receiver type"
            ),
            StringField("to_id", label="To ID", help_text="Receiver snowflake ID"),
            StringField("to_qiao_id", label="To Qiao ID", help_text="Receiver external ID"),
            IntegerEnumField(
                "service_provider",
                enum=ServiceProvider,
                label="Service Provider",
                help_text="Message service provider",
            ),
            IntegerEnumField(
                "message_type", enum=MessageType, label="Message Type", help_text="Type of message"
            ),
            TextAreaField("content", label="Content", help_text="Message content"),
            IntegerEnumField(
                "status", enum=MessageStatus, label="Status", help_text="Message status"
            ),
            "message_metadata",
            "created_at",
        ],
    )


class MediaFileView(ModelView):
    """Enhanced Media File view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "file_id",
        "upload_by_type",  # Auto-filled from admin user
        "upload_by_id",  # Auto-filled from admin user
        "upload_by_qiao_id",  # Auto-filled from admin user
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "file_id",
        "upload_by_type",  # Cannot change uploader
        "upload_by_id",  # Cannot change uploader
        "upload_by_qiao_id",  # Cannot change uploader
        "created_at",
        "updated_at",
    ]

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["file_id", "original_name"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "file_type",
        "file_size",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Internal file ID"),
            StringField("file_id", label="File ID", help_text="External file identifier"),
            IntegerEnumField(
                "file_type", enum=FileType, label="File Type", help_text="Type of media file"
            ),
            StringField(
                "category",
                label="Category",
                help_text="Optional secondary category",
                required=False,
            ),
            StringField(
                "original_name", label="Original Name", help_text="Original filename when uploaded"
            ),
            StringField("storage_provider", label="Storage Provider", help_text="Storage backend"),
            StringField(
                "bucket_name", label="Bucket Name", help_text="Cloud bucket", required=False
            ),
            StringField("object_key", label="Object Key", help_text="Object key in storage"),
            StringField(
                "storage_region",
                label="Storage Region",
                help_text="Storage region identifier",
                required=False,
            ),
            IntegerField("file_size", label="File Size (bytes)", help_text="File size in bytes"),
            StringField("mime_type", label="MIME Type", help_text="File MIME type"),
            StringField("file_hash", label="File Hash", help_text="SHA-256 hash", required=False),
            BooleanField("is_public", label="Public", help_text="Is publicly accessible"),
            StringField("etag", label="ETag", help_text="Storage provider ETag", required=False),
            IntegerEnumField(
                "upload_by_type",
                enum=UploaderType,
                label="Uploaded By Type",
                help_text="Type of uploader",
            ),
            StringField("upload_by_id", label="Uploader ID", help_text="Uploader snowflake ID"),
            StringField(
                "upload_by_qiao_id", label="Uploader Qiao ID", help_text="External ID of uploader"
            ),
            LocalDateTimeField(
                "confirmed_at",
                label="Confirmed At",
                help_text="Upload confirmation time",
                required=False,
            ),
            StringField(
                "confirmed_by_id",
                label="Confirmed By",
                help_text="Confirming operator ID",
                required=False,
            ),
            IntegerEnumField("status", enum=FileStatus, label="Status", help_text="File status"),
            LocalDateTimeField("created_at", label="Created At", help_text="File creation time"),
            LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )

    async def before_create(
        self,
        request: Request,
        data: MutableMapping[str, Any],
        obj: MediaFile,
    ) -> None:
        """Auto-fill uploader information from admin session."""
        # Get admin user from session
        admin_user = request.session.get("admin_user", {})
        admin_username = admin_user.get("username", "unknown")

        # Set uploader as admin
        obj.upload_by_type = UploaderType.ADMIN.value
        obj.upload_by_id = None  # Admin users don't have snowflake IDs
        obj.upload_by_qiao_id = admin_username  # Use admin username as identifier


class MessageDeliveryFailureView(ModelView):
    """Enhanced Message Delivery Failure view for failed message management."""

    label = "Message Failures"
    name = "Message Failures"

    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "msg_id_server",
        "from_id",
        "to_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = []

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = [
        "msg_id_server",
        "from_qiao_id",
        "to_qiao_id",
        "fail_reason_code",
    ]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "msg_id_server",
        "from_qiao_id",
        "to_qiao_id",
        "message_type",
        "service_provider",
        "retry_count",
        "max_retry_count",
        "next_retry_at",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("msg_id_server", label="Message ID", help_text="Original message ID"),
            IntegerEnumField(
                "from_type",
                enum=MessageParticipantType,
                label="Sender Type",
                help_text="Type of message sender",
            ),
            StringField("from_id", label="Sender ID", help_text="Sender snowflake ID"),
            StringField(
                "from_qiao_id", label="Sender Qiao ID", help_text="Sender external identifier"
            ),
            IntegerEnumField(
                "to_type",
                enum=MessageParticipantType,
                label="Receiver Type",
                help_text="Type of message receiver",
            ),
            StringField("to_id", label="Receiver ID", help_text="Receiver snowflake ID"),
            StringField(
                "to_qiao_id", label="Receiver Qiao ID", help_text="Receiver external identifier"
            ),
            IntegerEnumField(
                "message_type",
                enum=MessageType,
                label="Message Type",
                help_text="Type of failed message",
            ),
            IntegerEnumField(
                "service_provider",
                enum=ServiceProvider,
                label="Service Provider",
                help_text="Message service provider",
            ),
            TextAreaField("content", label="Message Content", help_text="Original message content"),
            StringField("fail_reason_code", label="Failure Code", help_text="Error reason code"),
            TextAreaField(
                "fail_detail", label="Failure Details", help_text="Detailed error information"
            ),
            IntegerField("retry_count", label="Retry Count", help_text="Current retry attempts"),
            IntegerField(
                "max_retry_count", label="Max Retries", help_text="Maximum retry attempts allowed"
            ),
            LocalDateTimeField(
                "next_retry_at", label="Next Retry", help_text="Scheduled next retry time"
            ),
            LocalDateTimeField(
                "created_at", label="Created At", help_text="Failure record creation time"
            ),
            LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )

    async def validate(
        self,
        request: Request,
        data: MutableMapping[str, object],
    ) -> None:
        """Custom validation for message delivery failures."""
        # Validate retry count
        if "retry_count" in data and "max_retry_count" in data:
            retry_count = _coerce_int(data["retry_count"], "retry_count")
            max_retry = _coerce_int(data["max_retry_count"], "max_retry_count")
            if retry_count > max_retry:
                raise FormValidationError(
                    {"retry_count": "Retry count cannot exceed maximum retries"}
                )

        # Validate message type
        if "message_type" in data:
            valid_types = [msg_type.value for msg_type in MessageType]
            message_type_value = _coerce_int(data["message_type"], "message_type")
            if message_type_value not in valid_types:
                raise FormValidationError({"message_type": "Invalid message type"})

        await super().validate(request, data)

    def can_delete(self, request: Request) -> bool:
        """Allow deletion of failure records after successful retry or manual resolution."""
        del request
        return True


# Create view instances
message_history_view = MessageHistoryView(
    MessageHistory, name="Message History", icon="fa fa-comments", identity="message_history"
)
media_file_view = MediaFileView(
    MediaFile, name="Media Files", icon="fa fa-file-image", identity="media_file"
)


class NotificationPushHistoryView(ModelView):
    """Notification Push History view - read-only for monitoring."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return False

    exclude_fields_from_list: ClassVar[list[str]] = []
    exclude_fields_from_create: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit: ClassVar[list[str]] = ["id", "created_at", "updated_at"]
    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["to_qiao_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "notification_type",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Notification record ID"),
            StringField("to_qiao_id", label="To Qiao ID", help_text="Receiver external ID"),
            IntegerEnumField(
                "notification_type",
                enum=NotificationType,
                label="Notification Type",
                help_text="Type of notification",
            ),
            JSONField("action_data", label="Action/Data", help_text="Action and data payload"),
            IntegerEnumField(
                "status",
                enum=NotificationStatus,
                label="Status",
                help_text="Delivery status",
            ),
            TextAreaField(
                "error_message", label="Error Message", help_text="Error details if failed"
            ),
            LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
            LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


message_delivery_failure_view = MessageDeliveryFailureView(
    MessageDeliveryFailure,
    name="Message Failures",
    icon="fa fa-exclamation-circle",
    identity="message_delivery_failure",
)

notification_push_history_view = NotificationPushHistoryView(
    NotificationPushHistory,
    name="Notification History",
    icon="fa fa-bell",
    identity="notification_push_history",
)

# Export all message and media views
MESSAGE_MEDIA_MODEL_VIEWS = [
    message_history_view,
    message_delivery_failure_view,
    notification_push_history_view,
    media_file_view,
]
