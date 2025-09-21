"""
Main Starlette-Admin configuration.
"""

from pathlib import Path
from starlette_admin.contrib.sqla import Admin
from starlette_admin import DropDown

from core.database import engine
from core.config import settings
from .auth import CustomAuthProvider
from .views import (
    # User Management
    user_view,
    profile_view,
    contact_view,
    # AI Management
    ai_character_view,
    ai_personality_view,
    ai_personality_placeholder_view,
    ai_style_view,
    ai_relationship_view,
    ai_relationship_dimension_view,
    ai_relationship_index_view,
    ai_info_template_view,
    ai_profile_template_view,
    ai_request_log_view,
    # Message Management
    message_history_view,
    # Media Management
    media_file_view,
    emoticon_view,
    # System Management
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    system_config_view,
    # LLM Management
    llm_provider_view,
    llm_config_view,
    # Security Management
    user_security_log_view,
    user_security_stats_view,
    # Session Management
    user_session_view,
    login_record_view,
    # Business Management
    contact_request_view,
    message_delivery_failure_view,
    # AI Extended Management
    ai_context_view,
    ai_relationship_score_view,
    # AI Testing (for routing only, not in menu)
    ai_character_chat_test_view,
    ai_score_algorithm_test_view,
    ai_relationship_index_api_view,
)
from .views.custom_views import (
    DashboardView,
    SystemSettingsView,
)

# Create admin instance with authentication and dashboard as index
admin = Admin(
    engine=engine,
    title="Qiao Dashboard",
    base_url="/qiao-dash",
    debug=settings.DEBUG,
    auth_provider=CustomAuthProvider(),
    templates_dir=str(Path(__file__).parent / "templates"),
    statics_dir=str(Path(__file__).parent / "static"),
    index_view=DashboardView(label="Dashboard", icon="fa fa-dashboard", path="/"),
)

# Menu groups with English labels (removed "Management" suffix and fixed "AI" spacing)
# Set always_open=False to make menus collapsed by default
user_group = DropDown(
    "Users",
    icon="fa fa-users",
    views=[user_view, profile_view, contact_view, contact_request_view],
    always_open=False,
)
admin.add_view(user_group)

message_group = DropDown(
    "Messages",
    icon="fa fa-comments",
    views=[message_history_view, message_delivery_failure_view],
    always_open=False,
)
admin.add_view(message_group)

ai_group = DropDown(
    "AI",
    icon="fa fa-robot",
    views=[
        ai_character_view,
        ai_personality_view,
        ai_personality_placeholder_view,
        ai_style_view,
        ai_relationship_view,
        ai_relationship_dimension_view,
        ai_relationship_index_view,
        ai_info_template_view,
        ai_profile_template_view,
        ai_request_log_view,
        ai_context_view,
        ai_relationship_score_view,
        ai_character_chat_test_view,
        ai_score_algorithm_test_view,
        ai_relationship_index_api_view,
    ],
    always_open=False,
)
admin.add_view(ai_group)

llm_group = DropDown(
    "LLM",
    icon="fa fa-brain",
    views=[
        llm_provider_view,
        llm_config_view,
    ],
    always_open=False,
)
admin.add_view(llm_group)

security_group = DropDown(
    "Security",
    icon="fa fa-shield",
    views=[
        user_security_log_view,
        user_security_stats_view,
    ],
    always_open=False,
)
admin.add_view(security_group)

session_group = DropDown(
    "Sessions",
    icon="fa fa-users",
    views=[
        user_session_view,
        login_record_view,
    ],
    always_open=False,
)
admin.add_view(session_group)

media_group = DropDown(
    "Media", icon="fa fa-file-image", views=[media_file_view, emoticon_view], always_open=False
)
admin.add_view(media_group)

system_group = DropDown(
    "System",
    icon="fa fa-cog",
    views=[
        SystemSettingsView(
            label="System Settings", icon="fa fa-cogs", path="/system-settings", methods=["GET", "POST"]
        ),
        system_config_view,
        admin_user_view,
        admin_operation_log_view,
        admin_login_log_view,
    ],
    always_open=False,
)
admin.add_view(system_group)

# Test views are now included in AI group with add_to_menu=False

# Development tools and testing functionality are now integrated into respective list views
