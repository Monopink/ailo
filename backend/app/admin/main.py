"""
Main Starlette-Admin configuration.
"""

import json
from pathlib import Path
from starlette_admin.contrib.sqla import Admin
from starlette_admin import CustomView
from starlette.responses import RedirectResponse
from starlette_admin import DropDown

from core.database import engine
from core.config import settings
from .auth import CustomAuthProvider
from .views import (
    # User Management
    user_view,
    profile_view,
    user_profile_log_view,
    contact_view,
    # AI Management
    ai_character_view,
    ai_personality_view,
    ai_personality_placeholder_view,
    ai_style_view,
    ai_relationship_view,
    ai_dimension_view,
    ai_style_dimension_view,
    ai_dimension_relationship_mapping_view,
    ai_character_template_view,
    ai_profile_template_view,
    ai_request_log_view,
    ai_message_buffer_view,
    ai_conversation_item_view,
    ai_conversation_item_archive_view,
    # Message Management
    message_history_view,
    notification_push_history_view,
    # Media Management
    media_file_view,
    preset_asset_view,
    # System Management
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
    system_config_view,
    # LLM Management
    llm_provider_view,
    llm_config_view,
    llm_test_log_view,
    # Security Management
    user_violation_log_view,
    user_risk_stats_view,
    # Token Management
    user_token_view,
    login_record_view,
    user_auth_view,
    # Business Management
    contact_request_view,
    message_delivery_failure_view,
    # AI Extended Management
    ai_character_dimension_view,
    # Statistics Management
    stats_user_daily_view,
    stats_user_weekly_view,
    stats_user_monthly_view,
    stats_revenue_daily_view,
    stats_revenue_weekly_view,
    stats_revenue_monthly_view,
    stats_message_daily_view,
    stats_message_weekly_view,
    stats_message_monthly_view,
    stats_ai_daily_view,
    stats_ai_weekly_view,
    stats_ai_monthly_view,
    # AI Testing (for routing only, not in menu)
    ai_character_chat_test_view,
    ai_style_test_view,
    # LLM Testing (for routing only, not in menu)
    llm_config_test_view,
)
from .views.dashboard_view import DashboardView
from .views.system_settings_view import SystemSettingsView
from .views.ai_advanced_edit_views import (
    character_advanced_edit_view,
    character_template_advanced_edit_view,
    personality_advanced_edit_view,
    style_advanced_edit_view,
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

# Configure Jinja2 tojson filter to display Chinese characters correctly
# Override starlette-admin's default tojson filter which uses ensure_ascii=True
admin.templates.env.filters["tojson"] = lambda data: json.dumps(data, default=str, ensure_ascii=False)

# Inject settings into template context
admin.templates.env.globals["settings"] = settings

# Ensure templates pick up changes without full restarts (dev-friendly)
# Enable auto reload and clear template cache so newly added overrides are used.
try:
    admin.templates.env.auto_reload = True
    # Clear any existing compiled template cache
    if hasattr(admin.templates.env, "cache") and isinstance(admin.templates.env.cache, dict):
        admin.templates.env.cache.clear()
except Exception:
    pass


# Add pretty JSON filter for structured display in detail/list views
def _pretty_json(data):
    try:
        return json.dumps(data, default=str, ensure_ascii=False, indent=2)
    except Exception:
        # Fallback to string if serialization fails
        return str(data)


admin.templates.env.filters["prettyjson"] = _pretty_json

# Menu groups with English labels (removed "Management" suffix and fixed "AI" spacing)
# Set always_open=False to make menus collapsed by default
user_group = DropDown(
    "Users",
    icon="fa fa-users",
    views=[
        user_view,
        profile_view,
        contact_view,
        contact_request_view,
        user_profile_log_view,
    ],
    always_open=False,
)
admin.add_view(user_group)

message_group = DropDown(
    "Messages",
    icon="fa fa-comments",
    views=[
        message_history_view,
        message_delivery_failure_view,
        notification_push_history_view,
    ],
    always_open=False,
)
admin.add_view(message_group)

ai_group = DropDown(
    "AI",
    icon="fa fa-robot",
    views=[
        ai_profile_template_view,
        ai_character_template_view,
        ai_character_view,
        ai_character_dimension_view,
        ai_style_view,
        ai_personality_view,
        ai_relationship_view,
        ai_dimension_view,
        ai_style_dimension_view,
        ai_personality_placeholder_view,
        ai_dimension_relationship_mapping_view,
        ai_message_buffer_view,
        ai_conversation_item_view,
        ai_conversation_item_archive_view,
        ai_request_log_view,
    ],
    always_open=False,
)
admin.add_view(ai_group)

# Register test views separately (not in menu, accessed via row actions only)
admin.add_view(ai_character_chat_test_view)
admin.add_view(ai_style_test_view)
admin.add_view(llm_config_test_view)

llm_group = DropDown(
    "LLM",
    icon="fa fa-brain",
    views=[
        llm_provider_view,
        llm_config_view,
        llm_test_log_view,
    ],
    always_open=False,
)
admin.add_view(llm_group)

security_group = DropDown(
    "Security",
    icon="fa fa-shield",
    views=[
        user_risk_stats_view,
        user_violation_log_view,
    ],
    always_open=False,
)
admin.add_view(security_group)

auth_group = DropDown(
    "Authorization",
    icon="fa fa-key",
    views=[
        user_auth_view,
        user_token_view,
        login_record_view,
    ],
    always_open=False,
)
admin.add_view(auth_group)

media_group = DropDown(
    "Media",
    icon="fa fa-file-image",
    views=[
        preset_asset_view,
        media_file_view,
    ],
    always_open=False,
)
admin.add_view(media_group)

# Statistics menu (flat structure, no nesting)
stats_group = DropDown(
    "Statistics",
    icon="fa fa-chart-bar",
    views=[
        stats_user_daily_view,
        stats_user_weekly_view,
        stats_user_monthly_view,
        stats_message_daily_view,
        stats_message_weekly_view,
        stats_message_monthly_view,
        stats_ai_daily_view,
        stats_ai_weekly_view,
        stats_ai_monthly_view,
        stats_revenue_daily_view,
        stats_revenue_weekly_view,
        stats_revenue_monthly_view,
    ],
    always_open=False,
)
admin.add_view(stats_group)

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

# Register advanced editing custom views (not in menu, accessed via buttons)
admin.add_view(character_advanced_edit_view)
admin.add_view(character_template_advanced_edit_view)
admin.add_view(personality_advanced_edit_view)
admin.add_view(style_advanced_edit_view)

# Test views are now included in AI group with add_to_menu=False

# Development tools and testing functionality are now integrated into respective list views


class ThemeSwitchView(CustomView):
    """
    Lightweight view to switch admin theme (SSR): sets cookie and redirects back.
    """

    async def render(self, request, templates):
        mode = str(request.path_params.get("mode", "light")).lower()
        if mode not in ("light", "dark", "auto"):
            mode = "light"
        referer = request.headers.get("referer") or str(request.url_for(admin.route_name + ":index"))
        response = RedirectResponse(url=referer, status_code=303)
        # Persist for 1 year
        response.set_cookie("qiao_admin_theme", mode, max_age=60 * 60 * 24 * 365, path="/", samesite="lax")
        return response


theme_switch_view = ThemeSwitchView(
    label="Theme Switch",
    name="theme_switch",
    path="/theme/{mode:str}",
    add_to_menu=False,
)
admin.add_view(theme_switch_view)
