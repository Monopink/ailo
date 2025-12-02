"""
Message and media-related model views for Starlette-Admin.
Creates ModelView instances for message system and media management.
"""

from typing import Any

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField
from enums import (
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
from models.message import MessageDeliveryFailure
from models.message.media import MediaFile
from models.message.message import MessageHistory
from models.message.notification import NotificationPushHistory
from models.system import PresetAsset
from starlette.requests import Request
from starlette_admin import IntegerField, JSONField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError


class MessageHistoryView(ModelView):
    """Enhanced Message History view - read-only for monitoring."""

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    exclude_fields_from_list = []
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conversation_id", "from_qiao_id", "to_qiao_id"]
    sortable_fields = ["id", "direction", "platform", "message_type", "status", "created_at"]

    fields = [
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
        IntegerEnumField("status", enum=MessageStatus, label="Status", help_text="Message status"),
        "message_metadata",
        "created_at",
    ]


class MediaFileView(ModelView):
    """Enhanced Media File view with proper field configuration."""

    exclude_fields_from_create = ["id", "file_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "file_id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["file_id", "original_name"]
    sortable_fields = ["id", "file_type", "file_size", "status", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Internal file ID"),
        StringField("file_id", label="File ID", help_text="External file identifier"),
        IntegerEnumField(
            "file_type", enum=FileType, label="File Type", help_text="Type of media file"
        ),
        StringField(
            "original_name", label="Original Name", help_text="Original filename when uploaded"
        ),
        StringField("file_path", label="File Path", help_text="Storage path of the file"),
        StringField("file_url", label="File URL", help_text="Public access URL"),
        IntegerField("file_size", label="File Size (bytes)", help_text="File size in bytes"),
        StringField("mime_type", label="MIME Type", help_text="File MIME type"),
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
        IntegerEnumField("status", enum=FileStatus, label="Status", help_text="File status"),
        LocalDateTimeField("created_at", label="Created At", help_text="File creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class MessageDeliveryFailureView(ModelView):
    """Enhanced Message Delivery Failure view for failed message management."""

    label = "Message Failures"
    name = "Message Failures"

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = [
        "id",
        "msg_id_server",
        "from_id",
        "to_id",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list = []

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["msg_id_server", "from_qiao_id", "to_qiao_id", "fail_reason_code"]
    sortable_fields = [
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

    fields = [
        StringField("msg_id_server", label="Message ID", help_text="Original message ID"),
        IntegerEnumField(
            "from_type",
            enum=MessageParticipantType,
            label="Sender Type",
            help_text="Type of message sender",
        ),
        StringField("from_id", label="Sender ID", help_text="Sender snowflake ID"),
        StringField("from_qiao_id", label="Sender Qiao ID", help_text="Sender external identifier"),
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
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for message delivery failures."""
        # Validate retry count
        if "retry_count" in data and "max_retry_count" in data:
            if data["retry_count"] > data["max_retry_count"]:
                raise FormValidationError(
                    {"retry_count": "Retry count cannot exceed maximum retries"}
                )

        # Validate message type
        if "message_type" in data:
            message_type = data["message_type"]
            valid_types = [msg_type.value for msg_type in MessageType]
            if message_type not in valid_types:
                raise FormValidationError({"message_type": "Invalid message type"})

        return await super().validate(request, data)

    def can_delete(self, request: Request) -> bool:
        """Allow deletion of failure records after successful retry or manual resolution."""
        return True


class PresetAssetView(ModelView):
    """Preset Asset view for managing avatars, emoticons, etc."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    fields_default_sort = [("asset_type", False), ("sort_order", False)]
    searchable_fields = ["name", "description"]
    sortable_fields = [
        "id",
        "asset_type",
        "category",
        "status",
        "sort_order",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Preset asset ID"),
        IntegerEnumField(
            "asset_type",
            choices=[(1, "Avatar"), (2, "Emoticon")],
            label="Asset Type",
            help_text="Type of preset asset",
            required=True,
        ),
        StringField("name", label="Name", help_text="Unique asset name", required=True),
        IntegerField("category", label="Category", help_text="Asset category", required=True),
        IntegerEnumField(
            "is_client_preset",
            choices=[(1, "Yes"), (0, "No")],
            label="Client Preset",
            help_text="Is bundled with client",
            required=False,
        ),
        IntegerField(
            "file_id", label="File ID", help_text="Media file ID (optional)", required=False
        ),
        StringField("url", label="URL", help_text="Asset URL", required=True),
        TextAreaField(
            "prompt", label="Prompt", help_text="AI generation prompt (optional)", required=False
        ),
        StringField(
            "description", label="Description", help_text="Asset description", required=False
        ),
        IntegerEnumField(
            "status",
            choices=[(1, "Active"), (2, "Inactive")],
            label="Status",
            help_text="Asset status",
            required=False,
        ),
        IntegerField("sort_order", label="Sort Order", help_text="Display order", required=False),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


# Create view instances
message_history_view = MessageHistoryView(
    MessageHistory, name="Message History", icon="fa fa-comments", identity="message_history"
)
media_file_view = MediaFileView(
    MediaFile, name="Media Files", icon="fa fa-file-image", identity="media_file"
)
preset_asset_view = PresetAssetView(
    PresetAsset, name="Preset Assets", icon="fa fa-image", identity="preset_assets"
)


class NotificationPushHistoryView(ModelView):
    """Notification Push History view - read-only for monitoring."""

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    exclude_fields_from_list = []
    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["to_qiao_id"]
    sortable_fields = ["id", "notification_type", "status", "created_at", "updated_at"]

    fields = [
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
        TextAreaField("error_message", label="Error Message", help_text="Error details if failed"),
        LocalDateTimeField("created_at", label="Created At", help_text="Creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


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
    preset_asset_view,
    media_file_view,
]
