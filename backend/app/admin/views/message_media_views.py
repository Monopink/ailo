"""Message and media-related model views for Starlette-Admin.
Creates ModelView instances for message system and media management.
"""

from collections.abc import MutableMapping, Sequence
from typing import Any, ClassVar, SupportsInt, cast

from starlette.requests import Request
from starlette_admin import (
    BooleanField,
    DateTimeField,
    HasOne,
    ImageField,
    IntegerField,
    JSONField,
    StringField,
    TextAreaField,
)
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField

from app.admin.views.base import IntegerEnumField
from app.enums import (
    FileStatus,
    FileType,
    MessageDeliveryStatus,
    MessageDirection,
    MessageDispatchOutboxStatus,
    MessageDispatchOutboxType,
    MessageParticipantType,
    MessageTransportProvider,
    MessageType,
    NotificationStatus,
    NotificationType,
    UploaderType,
)
from app.models.message import (
    MessageDelivery,
    MessageDevice,
    MessageDispatchOutbox,
    MessageEndpoint,
)
from app.models.message.media import MediaFile
from app.models.message.message import MessageHistory
from app.models.message.notification import NotificationPushHistory
from app.services.media.url import build_private_url, build_public_url


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


class _MediaFilePreviewField(ImageField):
    """Computed field showing media thumbnail when MIME type is image/*."""

    def __init__(
        self, name: str = "file_preview", label: str = "Preview", **kwargs: object
    ) -> None:
        super().__init__(name=name, label=label, **kwargs)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, _request: Request, obj: MediaFile) -> dict[str, str] | None:
        mime_type = (obj.mime_type or "").lower()
        if not mime_type.startswith("image/"):
            return None
        url = build_public_url(obj) if obj.is_public else build_private_url(obj)
        return {"url": url}


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
        "id",
        "conversation_id",
        "msg_id_server",
        "from_qiao_id",
        "to_qiao_id",
        "llm_request_id",
    ]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "direction",
        "message_type",
        "created_at",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Message history snowflake ID"),
            IntegerEnumField(
                "direction",
                enum=MessageDirection,
                label="Direction",
                help_text="Message direction",
            ),
            StringField(
                "conversation_id",
                label="Conversation ID",
                help_text="Conversation identifier",
            ),
            StringField(
                "msg_id_server",
                label="Server Message ID",
                help_text="Server-generated message ID",
            ),
            StringField(
                "msg_id_provider_inbound",
                label="Inbound Provider Message ID",
                help_text="Third-party provider message ID for inbound messages",
            ),
            StringField(
                "msg_id_client",
                label="Client Message ID",
                help_text="Client-generated message ID",
            ),
            DateTimeField(
                "client_sent_at",
                label="Client Sent At",
                help_text="Client-provided timestamp (optional)",
                required=False,
            ),
            DateTimeField(
                "sent_at",
                label="Sent At",
                help_text="Server-side event timestamp",
                required=False,
            ),
            IntegerEnumField(
                "from_type",
                enum=MessageParticipantType,
                label="From Type",
                help_text="Sender type",
            ),
            StringField("from_id", label="From ID", help_text="Sender snowflake ID"),
            StringField("from_qiao_id", label="From Qiao ID", help_text="Sender external ID"),
            IntegerEnumField(
                "to_type",
                enum=MessageParticipantType,
                label="To Type",
                help_text="Receiver type",
            ),
            StringField("to_id", label="To ID", help_text="Receiver snowflake ID"),
            StringField("to_qiao_id", label="To Qiao ID", help_text="Receiver external ID"),
            IntegerEnumField(
                "inbound_provider",
                enum=MessageTransportProvider,
                label="Inbound Provider",
                help_text="Inbound transport provider (inbound only)",
                required=False,
            ),
            StringField(
                "inbound_device_id",
                label="Inbound Device ID",
                help_text="Device UUID (websocket inbound only)",
                required=False,
            ),
            HasOne(
                "llm_request_log",
                identity="ai_request_log",
                label="LLM Request Log",
                help_text="Linked ai_request_logs row",
                required=False,
            ),
            IntegerEnumField(
                "message_type",
                enum=MessageType,
                label="Message Type",
                help_text="Type of message",
            ),
            TextAreaField("content", label="Content", help_text="Message content"),
            "message_metadata",
            DateTimeField(
                "created_at",
                label="Created At",
                help_text="Creation time",
            ),
        ],
    )


class MediaFileView(ModelView):
    """Enhanced Media File view with proper field configuration."""

    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "file_preview",
        "file_id",
        "upload_by_type",  # Auto-filled from admin user
        "upload_by_id",  # Auto-filled from admin user
        "upload_by_qiao_id",  # Auto-filled from admin user
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "file_preview",
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
            _MediaFilePreviewField(
                "file_preview",
                label="Preview",
                help_text="Image preview when MIME type is image/*",
            ),
            StringField("file_id", label="File ID", help_text="External file identifier"),
            IntegerEnumField(
                "file_type",
                enum=FileType,
                label="File Type",
                help_text="Type of media file",
            ),
            StringField(
                "category",
                label="Category",
                help_text="Optional secondary category",
                required=False,
            ),
            StringField(
                "original_name",
                label="Original Name",
                help_text="Original filename when uploaded",
            ),
            StringField(
                "storage_provider",
                label="Storage Provider",
                help_text="Storage backend",
            ),
            StringField(
                "bucket_name",
                label="Bucket Name",
                help_text="Cloud bucket",
                required=False,
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
                "upload_by_qiao_id",
                label="Uploader Qiao ID",
                help_text="External ID of uploader",
            ),
            DateTimeField(
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
            DateTimeField("created_at", label="Created At", help_text="File creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
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


class MessageDeliveryView(ModelView):
    """Delivery record view."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return True

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["msg_id_server", "target_key"]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Delivery ID"),
            StringField("msg_id_server", label="Msg ID Server", help_text="Timeline message ID"),
            StringField("endpoint_id", label="Endpoint ID", help_text="Delivery endpoint ID"),
            IntegerEnumField(
                "provider",
                enum=MessageTransportProvider,
                label="Provider",
                help_text="Transport provider",
            ),
            StringField("target_key", label="Target Key", help_text="Provider target identifier"),
            StringField(
                "provider_msg_id",
                label="Provider Msg ID",
                help_text="Third-party provider receipt ID (nullable)",
                required=False,
            ),
            IntegerEnumField(
                "status",
                enum=MessageDeliveryStatus,
                label="Status",
                help_text="Delivery status",
            ),
            DateTimeField(
                "dispatched_at",
                label="Dispatched At",
                help_text="Provider dispatched time",
                required=False,
            ),
            StringField(
                "failed_reason_code",
                label="Failed Reason Code",
                help_text="Failure code (nullable)",
                required=False,
            ),
            TextAreaField(
                "failed_detail",
                label="Failed Detail",
                help_text="Failure detail (nullable)",
                required=False,
            ),
            DateTimeField("created_at", label="Created At", help_text="Creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


# Create view instances
message_history_view = MessageHistoryView(
    MessageHistory,
    name="Message History",
    icon="fa fa-comments",
    identity="message_history",
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
                "error_message",
                label="Error Message",
                help_text="Error details if failed",
            ),
            DateTimeField("created_at", label="Created At", help_text="Creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


message_delivery_view = MessageDeliveryView(
    MessageDelivery,
    name="Message Deliveries",
    icon="fa fa-truck",
    identity="message_delivery",
)

notification_push_history_view = NotificationPushHistoryView(
    NotificationPushHistory,
    name="Notification History",
    icon="fa fa-bell",
    identity="notification_push_history",
)


class MessageDeviceView(ModelView):
    """Device-level cursor/state view."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return True

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("updated_at", True)]
    searchable_fields: ClassVar[list[str]] = ["user_qiao_id", "device_id"]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Record ID"),
            IntegerField("user_id", label="User ID", help_text="User internal ID"),
            StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
            StringField("device_id", label="Device ID", help_text="Device UUID"),
            StringField(
                "last_acked_msg_id",
                label="Last Ack Msg ID",
                help_text="Latest acknowledged msg_id_server",
                required=False,
            ),
            DateTimeField(
                "last_acked_msg_sent_at",
                label="Last Ack Sent At",
                help_text="Latest acknowledged message sent_at",
                required=False,
            ),
            DateTimeField(
                "last_pull_at",
                label="Last Pull At",
                help_text="Latest offline pull timestamp",
                required=False,
            ),
            DateTimeField(
                "last_seen_at",
                label="Last Seen At",
                help_text="Last seen timestamp",
                required=False,
            ),
            DateTimeField("created_at", label="Created At", help_text="Creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


class MessageEndpointView(ModelView):
    """Deliverable endpoint binding view."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return True

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("updated_at", True)]
    searchable_fields: ClassVar[list[str]] = ["user_qiao_id", "target_key", "device_id"]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Endpoint ID"),
            IntegerField("user_id", label="User ID", help_text="User internal ID"),
            StringField("user_qiao_id", label="User Qiao ID", help_text="User external ID"),
            StringField("device_id", label="Device ID", help_text="Device UUID"),
            IntegerEnumField(
                "provider",
                enum=MessageTransportProvider,
                label="Provider",
                help_text="Transport provider",
            ),
            StringField(
                "target_key",
                label="Target Key",
                help_text="websocket=device_id; leancloud=installation id",
            ),
            StringField(
                "client_kind",
                label="Client Kind",
                help_text="web/miniprogram/ios/android",
                required=False,
            ),
            DateTimeField(
                "lease_expires_at",
                label="Lease Expires At",
                help_text="Lease expiry time",
                required=False,
            ),
            DateTimeField(
                "last_seen_at",
                label="Last Seen At",
                help_text="Last seen timestamp",
                required=False,
            ),
            DateTimeField("created_at", label="Created At", help_text="Creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


class MessageDispatchOutboxView(ModelView):
    """Dispatch outbox queue view."""

    def can_create(self, request: Request) -> bool:
        del request
        return False

    def can_edit(self, request: Request) -> bool:
        del request
        return False

    def can_delete(self, request: Request) -> bool:
        del request
        return True

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = [
        "msg_id_server",
        "owner_user_id",
        "last_error_code",
    ]

    fields: ClassVar[Sequence[BaseField]] = cast(
        Sequence[BaseField],
        [
            StringField("id", label="ID", help_text="Outbox task ID"),
            IntegerEnumField(
                "outbox_type",
                enum=MessageDispatchOutboxType,
                label="Outbox Type",
                help_text="Dispatch task type",
            ),
            StringField(
                "msg_id_server",
                label="Msg ID Server",
                help_text="Timeline message ID",
            ),
            IntegerField(
                "owner_user_id",
                label="Owner User ID",
                help_text="Owner user internal ID",
            ),
            IntegerEnumField(
                "status",
                enum=MessageDispatchOutboxStatus,
                label="Status",
                help_text="Dispatch task status",
            ),
            IntegerField(
                "attempt_count",
                label="Attempt Count",
                help_text="Retry attempts count",
            ),
            DateTimeField(
                "next_retry_at",
                label="Next Retry At",
                help_text="Next retry schedule time",
                required=False,
            ),
            DateTimeField(
                "locked_at",
                label="Locked At",
                help_text="Current worker lock time",
                required=False,
            ),
            StringField(
                "last_error_code",
                label="Last Error Code",
                help_text="Last failure reason code",
                required=False,
            ),
            TextAreaField(
                "last_error_detail",
                label="Last Error Detail",
                help_text="Last failure detail",
                required=False,
            ),
            DateTimeField("created_at", label="Created At", help_text="Creation time"),
            DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
        ],
    )


message_device_view = MessageDeviceView(
    MessageDevice,
    name="Message Devices",
    icon="fa fa-mobile",
    identity="message_device",
)
message_endpoint_view = MessageEndpointView(
    MessageEndpoint,
    name="Message Endpoints",
    icon="fa fa-plug",
    identity="message_endpoint",
)
message_dispatch_outbox_view = MessageDispatchOutboxView(
    MessageDispatchOutbox,
    name="Message Dispatch Outbox",
    icon="fa fa-list-check",
    identity="message_dispatch_outbox",
)

# Export all message and media views
MESSAGE_MEDIA_MODEL_VIEWS = [
    message_history_view,
    message_delivery_view,
    message_device_view,
    message_endpoint_view,
    message_dispatch_outbox_view,
    notification_push_history_view,
    media_file_view,
]
