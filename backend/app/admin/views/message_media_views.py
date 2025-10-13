"""
Message and media-related model views for Starlette-Admin.
Creates ModelView instances for message system and media management.
"""

from starlette_admin.contrib.sqla import ModelView
from starlette_admin import IntegerField, JSONField, StringField, TextAreaField
from admin.views.base import IntegerEnumField

# Import message and media models
from models.message.message import MessageHistory
from models.message.media import MediaFile
from models.system.config import SystemConfig
from models.system import PresetAsset

# Import enums
from enums import (
    FileType,
    FileStatus,
    UploaderType,
    MessageDirection,
    MessageParticipantType,
    ServiceProvider,
    MessageType,
    MessageStatus,
    ConfigType,
)


class MessageHistoryView(ModelView):
    """Enhanced Message History view - read-only for monitoring."""

    def can_create(self, request):
        return False

    def can_edit(self, request):
        return False

    def can_delete(self, request):
        return False

    exclude_fields_from_list = ["content", "message_metadata", "updated_at"]
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
        StringField("conversation_id", label="Conversation ID", help_text="Conversation identifier"),
        StringField("msg_id_server", label="Server Message ID", help_text="Server-generated message ID"),
        StringField(
            "msg_id_provider", label="Provider Message ID", help_text="Third-party provider message ID"
        ),
        StringField("msg_id_client", label="Client Message ID", help_text="Client-generated message ID"),
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
    sortable_fields = ["id", "file_type", "file_size", "status", "created_at"]

    fields = [
        IntegerEnumField("file_type", enum=FileType, label="File Type", help_text="Type of media file"),
        StringField("original_name", label="Original Name", help_text="Original filename when uploaded"),
        StringField("file_path", label="File Path", help_text="Storage path of the file"),
        StringField("file_url", label="File URL", help_text="Public access URL"),
        IntegerField("file_size", label="File Size (bytes)", help_text="File size in bytes"),
        StringField("mime_type", label="MIME Type", help_text="File MIME type"),
        IntegerEnumField(
            "upload_by_type", enum=UploaderType, label="Uploaded By Type", help_text="Type of uploader"
        ),
        StringField("upload_by_id", label="Uploader ID", help_text="Uploader snowflake ID"),
        StringField("upload_by_qiao_id", label="Uploader Qiao ID", help_text="External ID of uploader"),
        IntegerEnumField("status", enum=FileStatus, label="Status", help_text="File status"),
    ]


class SystemConfigView(ModelView):
    """Enhanced System Config view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "updated_by"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "updated_by"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "description"]
    sortable_fields = ["id", "config_key", "config_type", "updated_at"]

    fields = [
        StringField("config_key", label="Config Key", help_text="Unique configuration key"),
        StringField("config_value", label="Config Value", help_text="Configuration value"),
        StringField("default_value", label="Default Value", help_text="Default configuration value"),
        IntegerEnumField(
            "config_type", enum=ConfigType, label="Config Type", help_text="Data type of the configuration"
        ),
        StringField("description", label="Description", help_text="Description of this configuration"),
        StringField("group_name", label="Group Name", help_text="Configuration group name"),
        JSONField(
            "allowed_values", label="Allowed Values", help_text="Allowed values for enum type (JSON array)"
        ),
        "updated_by",
    ]


class PresetAssetView(ModelView):
    """Preset Asset view for managing avatars, emoticons, etc."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    fields_default_sort = [("asset_type", False), ("sort_order", False)]
    searchable_fields = ["name", "description"]
    sortable_fields = ["id", "asset_type", "category", "status", "sort_order"]

    fields = [
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
        IntegerField("file_id", label="File ID", help_text="Media file ID (optional)", required=False),
        StringField("url", label="URL", help_text="Asset URL", required=True),
        TextAreaField(
            "prompt", label="Prompt", help_text="AI generation prompt (optional)", required=False
        ),
        StringField("description", label="Description", help_text="Asset description", required=False),
        IntegerEnumField(
            "status",
            choices=[(1, "Active"), (2, "Inactive")],
            label="Status",
            help_text="Asset status",
            required=False,
        ),
        IntegerField("sort_order", label="Sort Order", help_text="Display order", required=False),
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
system_config_view = SystemConfigView(
    SystemConfig, name="System Config", icon="fa fa-cog", identity="system_configs"
)

# Export all message and media views
MESSAGE_MEDIA_MODEL_VIEWS = [
    message_history_view,
    media_file_view,
    preset_asset_view,
    system_config_view,
]
