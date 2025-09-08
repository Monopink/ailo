"""
Model views for Starlette-Admin.
Creates ModelView instances for database models with proper field configuration.
"""

from starlette_admin.contrib.sqla import ModelView

# Import models
from models.admin import AdminUser, AdminOperationLog, AdminLoginLog
from models.user import User
from models.profile import Profile
from models.contact import Contact
from models.ai.character import AICharacter
from models.ai.personality import AIPersonality, AIPersonalityPlaceholder
from models.ai.style import AIStyle, AIRelationship
from models.ai.template import AIInfoTemplate, AIProfileTemplate
from models.ai.log import AIRequestLog
from models.message.message import MessageHistory
from models.message.media import MediaFile
from models.message.emoticon import Emoticon
from models.system.config import SystemConfig

# Create simple model views
admin_user_view = ModelView(AdminUser, name="Admin Users", icon="fa fa-users", identity="admin_user")
admin_operation_log_view = ModelView(AdminOperationLog, name="Operation Logs", icon="fa fa-list", identity="admin_operation_log")
admin_login_log_view = ModelView(AdminLoginLog, name="Login Logs", icon="fa fa-sign-in", identity="admin_login_log")

user_view = ModelView(User, name="Users", icon="fa fa-user", identity="user")
profile_view = ModelView(Profile, name="Profiles", icon="fa fa-id-card", identity="profile")
contact_view = ModelView(Contact, name="Contacts", icon="fa fa-address-book", identity="contact")

ai_character_view = ModelView(AICharacter, name="AI Characters", icon="fa fa-robot", identity="ai_character")
ai_personality_view = ModelView(AIPersonality, name="AI Personalities", icon="fa fa-brain", identity="ai_personality")
ai_personality_placeholder_view = ModelView(AIPersonalityPlaceholder, name="AI Personality Placeholders", icon="fa fa-tags", identity="ai_personality_placeholder")
ai_style_view = ModelView(AIStyle, name="AI Styles", icon="fa fa-palette", identity="ai_style")
ai_relationship_view = ModelView(AIRelationship, name="AI Relationships", icon="fa fa-heart", identity="ai_relationship")
ai_info_template_view = ModelView(AIInfoTemplate, name="AI Info Templates", icon="fa fa-file-text", identity="ai_info_template")
ai_profile_template_view = ModelView(AIProfileTemplate, name="AI Profile Templates", icon="fa fa-file-user", identity="ai_profile_template")

ai_request_log_view = ModelView(AIRequestLog, name="AI Request Logs", icon="fa fa-history", identity="ai_request_log")

message_history_view = ModelView(MessageHistory, name="Message History", icon="fa fa-comments", identity="message_history")
media_file_view = ModelView(MediaFile, name="Media Files", icon="fa fa-file-image", identity="media_file")
emoticon_view = ModelView(Emoticon, name="Emoticons", icon="fa fa-smile", identity="emoticon")
system_config_view = ModelView(SystemConfig, name="System Config", icon="fa fa-cog", identity="system_config")

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
