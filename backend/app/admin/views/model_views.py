"""
Model views for Starlette-Admin.
Creates ModelView instances for database models with enhanced field configuration.
"""

from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, HasOne, HasMany, IntegerField, StringField, TextAreaField
from starlette_admin.actions import link_row_action

# Import models
from models.admin import AdminUser, AdminOperationLog, AdminLoginLog
from models.user import User
from models.profile import Profile
from models.contact import Contact
from models.ai.character import AICharacter
from models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from models.ai.style import AIStyle, AIRelationship, AIRelationshipDimension
from models.ai.template import AIInfoTemplate, AIProfileTemplate
from models.ai.log import AIRequestLog
from models.message.message import MessageHistory
from models.message.media import MediaFile
from models.message.emoticon import Emoticon
from models.system.config import SystemConfig

# Import enums for dropdown fields
from enums import (
    UserStatus, UserType, AdminRole, AdminStatus,
    Gender, ProfileOwnerType, ContactType,
    AICharacterCreator, FileType, FileStatus, ConfigType,
    AICharacterStatus, UploaderType, EmoticonCategory, EmoticonCreatorType,
    MessageDirection, MessageParticipantType, ServiceProvider, MessageType, MessageStatus
)

# Define common status choices for models without specific enums
COMMON_STATUS_CHOICES = [(1, "Active"), (2, "Inactive")]
PLACEHOLDER_TYPE_CHOICES = [(1, "Text"), (2, "Number"), (3, "Boolean"), (4, "List")]
REQUIRED_CHOICES = [(0, "Optional"), (1, "Required")]
REUSABLE_CHOICES = [(0, "Single Use"), (1, "Reusable")]

# Enhanced ModelView classes with proper field configuration

class AdminUserView(ModelView):
    """Enhanced AdminUser view with proper field configuration."""

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields = [
        StringField("username", label="Username", help_text="Administrator username"),
        EnumField("role", enum=AdminRole, label="Role", help_text="Administrator role level"),
        EnumField("status", enum=AdminStatus, label="Status", help_text="Account status"),
        "last_login",
        "login_count",
        "created_by",
        "created_at",
        "updated_at"
    ]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username"]
    sortable_fields = ["id", "username", "role", "status", "created_at", "last_login"]
    exclude_fields_from_list = ["password_hash"]
    exclude_fields_from_detail = ["password_hash"]
    exclude_fields_from_create = ["id", "created_at", "updated_at", "last_login", "login_count", "created_by"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "last_login", "login_count", "created_by"]

class UserView(ModelView):
    """Enhanced User view with proper field configuration."""

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at", "last_login"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at", "last_login"]
    exclude_fields_from_list = ["password_hash", "wechat_openid", "apple_id"]
    exclude_fields_from_detail = ["password_hash"]

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "phone", "email", "qiao_id"]
    sortable_fields = ["id", "username", "qiao_id", "status", "user_type", "created_at", "last_login"]

    fields = [
        "qiao_id",
        StringField("username", label="Username", help_text="Display name for the user"),
        StringField("phone", label="Phone Number", help_text="Phone number for login"),
        StringField("email", label="Email Address", help_text="Email address for notifications"),
        EnumField("status", enum=UserStatus, label="Account Status", help_text="Current account status"),
        EnumField("user_type", enum=UserType, label="User Type", help_text="User classification"),
        "last_login",
        "created_at",
        "updated_at"
    ]

class AIPersonalityView(ModelView):
    """Enhanced AI Personality view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["json_schema", "prompt"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("name", label="Personality Name", help_text="Unique identifier for the personality"),
        StringField("display_name", label="Display Name", help_text="Human-readable name shown in UI"),
        TextAreaField("prompt", label="Personality Prompt", help_text="Template for AI personality behavior"),
        "json_schema",
        IntegerField("typing_speed", label="Typing Speed (CPM)", help_text="Characters per minute typing speed"),
        EnumField("status", choices=COMMON_STATUS_CHOICES, label="Status", help_text="Active personalities can be used"),
    ]

class AIPersonalityPlaceholderView(ModelView):
    """Enhanced AI Personality Placeholder view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "validation_rules"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]
    exclude_fields_from_list = ["validation_rules", "example_value"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("personality_id", False), ("placeholder_key", False)]
    searchable_fields = ["placeholder_key", "display_name"]
    sortable_fields = ["id", "personality_id", "placeholder_key", "display_name", "placeholder_type", "is_required"]

    fields = [
        HasOne("personality_id", identity="ai_personality", label="Personality",
               help_text="Select the AI personality this placeholder belongs to"),
        StringField("placeholder_key", label="Placeholder Key",
                   help_text="Variable name used in prompt template (e.g., {name})"),
        StringField("display_name", label="Display Name",
                   help_text="Human-readable name for this placeholder"),
        StringField("description", label="Description",
                   help_text="Explanation of what this placeholder represents"),
        TextAreaField("example_value", label="Example Value",
                     help_text="Sample value to help users understand the placeholder"),
        EnumField("placeholder_type",
                 choices=PLACEHOLDER_TYPE_CHOICES,
                 label="Placeholder Type", help_text="Data type for validation"),
        EnumField("is_required",
                 choices=REQUIRED_CHOICES,
                 label="Required", help_text="Whether this placeholder must be filled"),
    ]

# Enhanced AI Character view with chat test functionality
class AICharacterView(ModelView):
    """Enhanced AI Character view with proper field configuration and chat test functionality."""

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_variables", "memory"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "category"]
    sortable_fields = ["id", "qiao_id", "category", "status", "created_by", "created_at"]

    fields = [
        StringField("category", label="Category", help_text="Character category classification"),
        HasOne("user_id", identity="user", label="Owner User",
               help_text="Select the user who owns this character (optional for system characters)"),
        HasOne("style_id", identity="ai_style", label="AI Style",
               help_text="Select the AI style for this character"),
        HasOne("personality_id", identity="ai_personality", label="AI Personality",
               help_text="Select the AI personality for this character"),
        EnumField("status", enum=AICharacterStatus, label="Status",
                 help_text="Character status: Active characters can be used"),
        TextAreaField("memory", label="Memory Settings",
                     help_text="Character-specific memory and background information"),
        "prompt_variables",
        StringField("score_offset_algorithm", label="Score Offset Algorithm",
                   help_text="Algorithm for relationship score calculation"),
        "score_offset_coefficient",
        EnumField("created_by", choices=[(1, "System"), (2, "User"), (3, "Admin")],
                 label="Created By", help_text="Who created this character"),
    ]

    # Add row actions including the default ones and our custom chat test
    row_actions = ["view", "edit", "chat_test"]

    @link_row_action(
        name="chat_test",
        text="Chat Test",
        icon_class="fas fa-comment-dots",
    )
    def chat_test_row_action(self, request, pk):
        """Custom row action to test chat with this AI character."""
        return f"/admin/ai-character-chat-test?character_ids={pk}"

# Enhanced AI Style view
class AIStyleView(ModelView):
    """Enhanced AI Style view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("name", label="Style Name", help_text="Unique identifier for the style"),
        StringField("display_name", label="Display Name", help_text="Human-readable name shown in UI"),
        HasOne("initial_relationship_id", identity="ai_relationship", label="Initial Relationship",
               help_text="Default relationship type when character is created"),
        EnumField("status", choices=COMMON_STATUS_CHOICES, label="Status",
                 help_text="Active styles can be used"),
    ]

# Enhanced AI Relationship view
class AIRelationshipView(ModelView):
    """Enhanced AI Relationship view with proper field configuration."""

    exclude_fields_from_create = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "usage_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_fragment"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["name", "display_name"]
    sortable_fields = ["id", "name", "display_name", "status", "usage_count", "created_at"]

    fields = [
        StringField("name", label="Relationship Name", help_text="Unique identifier for the relationship"),
        StringField("display_name", label="Display Name", help_text="Human-readable name shown in UI"),
        TextAreaField("prompt_fragment", label="Prompt Fragment",
                     help_text="Text fragment to be included in AI prompts for this relationship"),
        EnumField("status", choices=COMMON_STATUS_CHOICES, label="Status",
                 help_text="Active relationships can be used"),
    ]

# Enhanced AI Template views
class AIInfoTemplateView(ModelView):
    """Enhanced AI Info Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "profile_count", "created_at", "updated_at"]
    exclude_fields_from_list = ["prompt_variables", "score_offset_params"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = []
    sortable_fields = ["id", "style_id", "personality_id", "status", "is_reusable", "created_at"]

    fields = [
        HasOne("style_id", identity="ai_style", label="AI Style",
               help_text="Select the AI style for this template"),
        HasOne("personality_id", identity="ai_personality", label="AI Personality",
               help_text="Select the AI personality for this template"),
        TextAreaField("memory", label="Memory Settings",
                     help_text="Default memory settings for characters using this template"),
        "prompt_variables",
        StringField("score_offset_algorithm", label="Score Offset Algorithm",
                   help_text="Algorithm for relationship score calculation"),
        "score_offset_params",
        EnumField("is_reusable", choices=REUSABLE_CHOICES, label="Reusable",
                 help_text="Whether this template can be used multiple times"),
        IntegerField("profile_id", label="Profile ID", help_text="Associated profile ID (for single-use templates)"),
        EnumField("status", choices=COMMON_STATUS_CHOICES, label="Status",
                 help_text="Active templates can be used"),
    ]

class AIProfileTemplateView(ModelView):
    """Enhanced AI Profile Template view with proper field configuration."""

    exclude_fields_from_create = ["id", "qiao_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "qiao_id", "created_at", "updated_at"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["qiao_id", "nickname", "category"]
    sortable_fields = ["id", "qiao_id", "category", "nickname", "gender", "status", "is_reusable", "created_at"]

    fields = [
        StringField("qiao_id", label="External ID", help_text="External identifier for this template"),
        StringField("category", label="Category", help_text="Profile template category"),
        HasOne("info_id", identity="ai_info_template", label="Info Template",
               help_text="Select the associated AI info template"),
        StringField("nickname", label="Nickname", help_text="Character nickname"),
        EnumField("gender", enum=Gender, label="Gender", help_text="Character gender"),
        StringField("avatar_url", label="Avatar URL", help_text="Character avatar image URL"),
        TextAreaField("bio", label="Bio", help_text="Character biography and description"),
        StringField("region", label="Region", help_text="Character location/region"),
        EnumField("is_reusable", choices=REUSABLE_CHOICES, label="Reusable",
                 help_text="Whether this template can be used multiple times"),
        EnumField("status", choices=COMMON_STATUS_CHOICES, label="Status",
                 help_text="Active templates can be used"),
    ]

# Enhanced AI Request Log view (read-only)
class AIRequestLogView(ModelView):
    """Enhanced AI Request Log view - read-only for monitoring."""

    exclude_fields_from_create = ["id", "character_id", "user_id", "style_id", "personality_id",
                                  "request", "response", "status", "token_count", "response_time", "created_at"]
    exclude_fields_from_edit = ["id", "character_id", "user_id", "style_id", "personality_id",
                               "request", "response", "status", "token_count", "response_time", "created_at"]
    exclude_fields_from_list = ["request", "response"]

    # Read-only view - disable all modifications
    can_create = False
    can_edit = False
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = []
    sortable_fields = ["id", "character_id", "user_id", "status", "token_count", "response_time", "created_at"]

    fields = [
        HasOne("character_id", identity="ai_character", label="AI Character"),
        HasOne("user_id", identity="user", label="User"),
        HasOne("style_id", identity="ai_style", label="AI Style"),
        HasOne("personality_id", identity="ai_personality", label="AI Personality"),
        EnumField("status", choices=[(1, "Success"), (2, "Failed"), (3, "Timeout")], label="Status"),
        IntegerField("token_count", label="Token Count"),
        IntegerField("response_time", label="Response Time (ms)"),
        "created_at",
    ]

# Create view instances with identity for relationship fields
admin_user_view = AdminUserView(AdminUser, name="Admin Users", icon="fa fa-users", identity="admin_user")
# Enhanced log views - read-only
class AdminOperationLogView(ModelView):
    """Enhanced Admin Operation Log view - read-only for monitoring."""

    # Read-only view - disable all modifications
    can_create = False
    can_edit = False
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["resource_name", "operation_desc"]
    sortable_fields = ["id", "admin_user_id", "operation_type", "resource_type", "created_at"]

class AdminLoginLogView(ModelView):
    """Enhanced Admin Login Log view - read-only for monitoring."""

    # Read-only view - disable all modifications
    can_create = False
    can_edit = False
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "ip_address"]
    sortable_fields = ["id", "admin_user_id", "username", "result", "created_at"]

# Enhanced other model views
class ProfileView(ModelView):
    """Enhanced Profile view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["nickname", "owner_qiao_id"]
    sortable_fields = ["id", "owner_type", "nickname", "gender", "created_at"]

    fields = [
        IntegerField("owner_id", label="Owner ID", help_text="Internal ID of the profile owner"),
        StringField("owner_qiao_id", label="Owner External ID", help_text="External ID of the profile owner"),
        EnumField("owner_type", enum=ProfileOwnerType, label="Owner Type", help_text="Type of profile owner"),
        StringField("nickname", label="Nickname", help_text="Display nickname"),
        EnumField("gender", enum=Gender, label="Gender", help_text="Gender information"),
        HasOne("avatar_file_id", identity="media_file", label="Avatar File",
               help_text="Select avatar file from media library"),
        StringField("avatar_url", label="Avatar URL", help_text="Profile avatar image URL"),
        TextAreaField("avatar_prompt", label="Avatar Prompt", help_text="Description for AI-generated avatars"),
        TextAreaField("bio", label="Bio", help_text="Profile biography"),
        StringField("region", label="Region", help_text="Location/region information"),
    ]

class ContactView(ModelView):
    """Enhanced Contact view with proper field configuration."""

    exclude_fields_from_create = ["id", "conv_id", "created_at", "updated_at", "deleted_at"]
    exclude_fields_from_edit = ["id", "conv_id", "created_at", "updated_at", "deleted_at"]
    exclude_fields_from_list = ["tags", "remark"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["conv_id", "user_qiao_id", "contact_qiao_id", "alias"]
    sortable_fields = ["id", "contact_type", "alias", "is_pinned", "is_muted", "is_blocked", "created_at"]

    fields = [
        StringField("conv_id", label="Conversation ID", help_text="Unique conversation identifier"),
        HasOne("user_id", identity="user", label="Owner User", help_text="Select the user who owns this contact"),
        StringField("user_qiao_id", label="User External ID", help_text="Owner user external ID"),
        EnumField("contact_type", enum=ContactType, label="Contact Type", help_text="Type of contact"),
        IntegerField("contact_id", label="Contact Internal ID", help_text="Contact internal ID"),
        StringField("contact_qiao_id", label="Contact External ID", help_text="Contact external ID"),
        StringField("alias", label="Alias", help_text="Custom name for this contact"),
        StringField("avatar_alias_url", label="Custom Avatar", help_text="Custom avatar URL"),
        "tags",
        TextAreaField("remark", label="Remark", help_text="Additional notes about this contact"),
        EnumField("is_pinned", choices=[(0, "No"), (1, "Yes")], label="Pinned", help_text="Pin to top of contact list"),
        EnumField("is_muted", choices=[(0, "No"), (1, "Yes")], label="Muted", help_text="Mute notifications"),
        EnumField("is_blocked", choices=[(0, "No"), (1, "Yes")], label="Blocked", help_text="Block this contact"),
        EnumField("is_deleted", choices=[(0, "No"), (1, "Yes")], label="Deleted", help_text="Soft delete status"),
    ]

admin_operation_log_view = AdminOperationLogView(AdminOperationLog, name="Operation Logs", icon="fa fa-list", identity="admin_operation_log")
admin_login_log_view = AdminLoginLogView(AdminLoginLog, name="Login Logs", icon="fa fa-sign-in", identity="admin_login_log")

user_view = UserView(User, name="Users", icon="fa fa-user", identity="user")
profile_view = ProfileView(Profile, name="Profiles", icon="fa fa-id-card", identity="profile")
contact_view = ContactView(Contact, name="Contacts", icon="fa fa-address-book", identity="contact")

ai_character_view = AICharacterView(AICharacter, name="AI Characters", icon="fa fa-robot", identity="ai_character")
ai_personality_view = AIPersonalityView(AIPersonality, name="AI Personalities", icon="fa fa-brain", identity="ai_personality")
ai_personality_placeholder_view = AIPersonalityPlaceholderView(AIPersonalityPlaceholder, name="AI Personality Placeholders", icon="fa fa-tags", identity="ai_personality_placeholder")
ai_style_view = AIStyleView(AIStyle, name="AI Styles", icon="fa fa-palette", identity="ai_style")
ai_relationship_view = AIRelationshipView(AIRelationship, name="AI Relationships", icon="fa fa-heart", identity="ai_relationship")
ai_info_template_view = AIInfoTemplateView(AIInfoTemplate, name="AI Info Templates", icon="fa fa-file-text", identity="ai_info_template")
ai_profile_template_view = AIProfileTemplateView(AIProfileTemplate, name="AI Profile Templates", icon="fa fa-file-user", identity="ai_profile_template")
ai_request_log_view = AIRequestLogView(AIRequestLog, name="AI Request Logs", icon="fa fa-history", identity="ai_request_log")

# Enhanced other model views with delete protection
class MessageHistoryView(ModelView):
    """Enhanced Message History view - read-only for monitoring."""

    # Read-only view - disable all modifications
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
        EnumField("platform", choices=[(1, "iOS"), (2, "Android"), (3, "Web"), (4, "Mini Program")],
                 label="Platform", help_text="Source platform"),
        StringField("conversation_id", label="Conversation ID", help_text="Conversation identifier"),
        StringField("msg_id_server", label="Server Message ID", help_text="Server-generated message ID"),
        StringField("msg_id_provider", label="Provider Message ID", help_text="Third-party provider message ID"),
        StringField("msg_id_client", label="Client Message ID", help_text="Client-generated message ID"),
        "client_sent_time",
        EnumField("from_type", enum=MessageParticipantType, label="From Type", help_text="Sender type"),
        IntegerField("from_id", label="From ID", help_text="Sender internal ID"),
        StringField("from_qiao_id", label="From External ID", help_text="Sender external ID"),
        EnumField("to_type", enum=MessageParticipantType, label="To Type", help_text="Receiver type"),
        IntegerField("to_id", label="To ID", help_text="Receiver internal ID"),
        StringField("to_qiao_id", label="To External ID", help_text="Receiver external ID"),
        EnumField("service_provider", enum=ServiceProvider, label="Service Provider", help_text="Message service provider"),
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

    # Disable delete operations to prevent physical deletion
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
        EnumField("upload_by_type", enum=UploaderType, label="Uploaded By Type", help_text="Type of uploader"),
        IntegerField("upload_by_id", label="Uploader ID", help_text="Internal ID of uploader"),
        StringField("upload_by_qiao_id", label="Uploader External ID", help_text="External ID of uploader"),
        EnumField("status", enum=FileStatus, label="Status", help_text="File status"),
    ]

class EmoticonView(ModelView):
    """Enhanced Emoticon view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    # Disable delete operations to prevent physical deletion
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
        EnumField("created_by_type", enum=EmoticonCreatorType, label="Created By Type", help_text="Type of creator"),
        IntegerField("created_by_id", label="Creator ID", help_text="ID of creator"),
        EnumField("status", choices=[(1, "Active"), (2, "Inactive")],
                 label="Status", help_text="Emoticon status"),
        IntegerField("sort_order", label="Sort Order", help_text="Display order"),
    ]

class SystemConfigView(ModelView):
    """Enhanced System Config view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at"]

    # Disable delete operations to prevent physical deletion
    def can_delete(self, request):
        return False

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "description"]
    sortable_fields = ["id", "config_key", "config_type", "is_public", "updated_at"]

    fields = [
        StringField("config_key", label="Config Key", help_text="Unique configuration key"),
        StringField("config_value", label="Config Value", help_text="Configuration value"),
        EnumField("config_type", enum=ConfigType, label="Config Type", help_text="Data type of the configuration"),
        StringField("description", label="Description", help_text="Description of this configuration"),
        EnumField("is_public", choices=[(0, "Private"), (1, "Public")], label="Visibility",
                 help_text="Whether this config is publicly accessible"),
        "updated_by",
    ]

message_history_view = MessageHistoryView(MessageHistory, name="Message History", icon="fa fa-comments", identity="message_history")
media_file_view = MediaFileView(MediaFile, name="Media Files", icon="fa fa-file-image", identity="media_file")
emoticon_view = EmoticonView(Emoticon, name="Emoticons", icon="fa fa-smile", identity="emoticon")
system_config_view = SystemConfigView(SystemConfig, name="System Config", icon="fa fa-cog", identity="system_config")

# List of all model views for easy import
ALL_MODEL_VIEWS = [
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    user_view,
    profile_view,
    contact_view,
    ai_character_view,
    ai_personality_view,
    ai_personality_placeholder_view,
    ai_style_view,
    ai_relationship_view,
    ai_info_template_view,
    ai_profile_template_view,
    ai_request_log_view,
    message_history_view,
    media_file_view,
    emoticon_view,
    system_config_view,
]
