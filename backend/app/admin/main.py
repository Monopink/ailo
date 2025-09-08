"""
Main Starlette-Admin configuration.
"""

from starlette_admin.contrib.sqla import Admin
from starlette_admin import DropDown

from core.database import engine
from core.config import settings
from .auth import CustomAuthProvider
from .views.model_views import (
    # User Management
    user_view, profile_view, contact_view,
    # AI Management
    ai_character_view, ai_personality_view, ai_personality_placeholder_view, ai_style_view, ai_relationship_view,
    ai_info_template_view, ai_profile_template_view, ai_request_log_view,
    # Message Management
    message_history_view,
    # Media Management
    media_file_view, emoticon_view,
    # System Management
    admin_user_view, admin_operation_log_view, admin_login_log_view, system_config_view,
)
from .views.custom_views import (
    AICharacterChatTestView,
    SendMessageView,
    LLMTestView,
    DashboardView,
)

# Create admin instance with authentication and dashboard as index
admin = Admin(
    engine=engine,
    title="Qiao Panel",
    base_url="/qiao-panel",
    debug=settings.DEBUG,
    auth_provider=CustomAuthProvider(),
    templates_dir="admin/templates",
    statics_dir="admin/static",
    index_view=DashboardView(label="Dashboard", icon="fa fa-dashboard", path="/"),
)

# Menu groups with English labels (removed "Management" suffix and fixed "AI" spacing)
user_group = DropDown(
    "Users",
    icon="fa fa-users",
    views=[user_view, profile_view, contact_view]
)
admin.add_view(user_group)

message_group = DropDown(
    "Messages",
    icon="fa fa-comments",
    views=[message_history_view]
)
admin.add_view(message_group)

ai_group = DropDown(
    "AI",
    icon="fa fa-robot",
    views=[
        ai_character_view, ai_personality_view, ai_personality_placeholder_view, ai_style_view, ai_relationship_view,
        ai_info_template_view, ai_profile_template_view, ai_request_log_view
    ]
)
admin.add_view(ai_group)

media_group = DropDown(
    "Media",
    icon="fa fa-file-image",
    views=[media_file_view, emoticon_view]
)
admin.add_view(media_group)

system_group = DropDown(
    "System",
    icon="fa fa-cog",
    views=[system_config_view, admin_user_view, admin_operation_log_view, admin_login_log_view]
)
admin.add_view(system_group)

tools_group = DropDown(
    "Development Tools",
    icon="fa fa-tools",
    views=[
        SendMessageView(label="Send Message", icon="fa fa-paper-plane", path="/send-message"),
        LLMTestView(label="LLM Test", icon="fa fa-flask", path="/llm-test")
    ]
)
admin.add_view(tools_group)

# Add custom route for AI Character Chat Test
admin.add_view(AICharacterChatTestView(label="AI Character Chat Test", icon="fa fa-comment-dots", path="/ai-character-chat-test"))
