"""
Message and media-related model views for Starlette-Admin.
Creates ModelView instances for message system and media management.
"""

from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, HasOne, IntegerField, StringField, TextAreaField

# Import message and media models
from models.message.message import MessageHistory
from models.message.media import MediaFile
from models.message.emoticon import Emoticon
from models.system.config import SystemConfig

# Import enums
from enums import (
    FileType,
    FileStatus,
    UploaderType,
    EmoticonCategory,
    EmoticonCreatorType,
    MessageDirection,
    MessageParticipantType,
    ServiceProvider,
    MessageType,
    MessageStatus,
    ConfigType,
)


class MessageHistoryView(ModelView):
    """Enhanced Message History view - read-only for monitoring."""

    can_create = False
    can_edit = False

    def can_delete(self, request):
        return False

    exclude_fields_from_list = ["content", "message_metadata"]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conversation_id", "from_qiao_id", "to_qiao_id"]
    sortable_fields = ["id", "direction", "platform", "message_type", "status", "created_at"]

    fields = [
        EnumField("direction", enum=MessageDirection, label="Direction", help_text="Message direction"),
        EnumField(
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
        EnumField("from_type", enum=MessageParticipantType, label="From Type", help_text="Sender type"),
        IntegerField("from_id", label="From ID", help_text="Sender internal ID"),
        StringField("from_qiao_id", label="From External ID", help_text="Sender external ID"),
        EnumField("to_type", enum=MessageParticipantType, label="To Type", help_text="Receiver type"),
        IntegerField("to_id", label="To ID", help_text="Receiver internal ID"),
        StringField("to_qiao_id", label="To External ID", help_text="Receiver external ID"),
        EnumField(
            "service_provider",
            enum=ServiceProvider,
            label="Service Provider",
            help_text="Message service provider",
        ),
        EnumField("message_type", enum=MessageType, label="Message Type", help_text="Type of message"),
        TextAreaField("content", label="Content", help_text="Message content"),
        EnumField("status", enum=MessageStatus, label="Status", help_text="Message status"),
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
        EnumField("file_type", enum=FileType, label="File Type", help_text="Type of media file"),
        StringField("original_name", label="Original Name", help_text="Original filename when uploaded"),
        StringField("file_path", label="File Path", help_text="Storage path of the file"),
        StringField("file_url", label="File URL", help_text="Public access URL"),
        IntegerField("file_size", label="File Size (bytes)", help_text="File size in bytes"),
        StringField("mime_type", label="MIME Type", help_text="File MIME type"),
        EnumField(
            "upload_by_type", enum=UploaderType, label="Uploaded By Type", help_text="Type of uploader"
        ),
        IntegerField("upload_by_id", label="Uploader ID", help_text="Internal ID of uploader"),
        StringField("upload_by_qiao_id", label="Uploader External ID", help_text="External ID of uploader"),
        EnumField("status", enum=FileStatus, label="Status", help_text="File status"),
    ]


class EmoticonView(ModelView):
    """Enhanced Emoticon view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("sort_order", False), ("created_at", True)]
    searchable_fields = ["code", "description"]
    sortable_fields = ["id", "code", "category", "status", "sort_order", "created_at"]

    fields = [
        StringField("code", label="Emoticon Code", help_text="Unique identifier for the emoticon"),
        EnumField("category", enum=EmoticonCategory, label="Category", help_text="Emoticon category"),
        HasOne("file_id", identity="media_file", label="File", help_text="Select emoticon file"),
        StringField("url", label="URL", help_text="Direct URL to emoticon image"),
        StringField("description", label="Description", help_text="Emoticon description"),
        EnumField(
            "created_by_type",
            enum=EmoticonCreatorType,
            label="Created By Type",
            help_text="Type of creator",
        ),
        IntegerField("created_by_id", label="Creator ID", help_text="ID of creator"),
        EnumField(
            "status", choices=[(1, "Active"), (2, "Inactive")], label="Status", help_text="Emoticon status"
        ),
        IntegerField("sort_order", label="Sort Order", help_text="Display order"),
    ]


class SystemConfigView(ModelView):
    """Enhanced System Config view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    def can_delete(self, request):
        return False

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "description"]
    sortable_fields = ["id", "config_key", "config_type", "is_public", "updated_at"]

    fields = [
        StringField("config_key", label="Config Key", help_text="Unique configuration key"),
        StringField("config_value", label="Config Value", help_text="Configuration value"),
        EnumField(
            "config_type", enum=ConfigType, label="Config Type", help_text="Data type of the configuration"
        ),
        StringField("description", label="Description", help_text="Description of this configuration"),
        EnumField(
            "is_public",
            choices=[(0, "Private"), (1, "Public")],
            label="Visibility",
            help_text="Whether this config is publicly accessible",
        ),
        "updated_by",
    ]


# Create view instances
message_history_view = MessageHistoryView(
    MessageHistory, name="Message History", icon="fa fa-comments", identity="message_history"
)
media_file_view = MediaFileView(
    MediaFile, name="Media Files", icon="fa fa-file-image", identity="media_file"
)
emoticon_view = EmoticonView(Emoticon, name="Emoticons", icon="fa fa-smile", identity="emoticon")
system_config_view = SystemConfigView(
    SystemConfig, name="System Config", icon="fa fa-cog", identity="system_config"
)

# Export all message and media views
MESSAGE_MEDIA_MODEL_VIEWS = [
    message_history_view,
    media_file_view,
    emoticon_view,
    system_config_view,
]