"""Main Starlette-Admin configuration."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette_admin import CustomView, DropDown, TimezoneConfig
from starlette_admin.contrib.sqla import Admin

from app.core.config import Settings, get_settings
from app.core.database import get_engine

from .auth import CustomAuthProvider
from .i18n import admin_text, build_i18n_config, translate_labels
from .views import (
    admin_login_log_view,
    admin_operation_log_view,
    admin_user_view,
    ai_conversation_item_archive_view,
    ai_conversation_item_view,
    ai_conversation_runtime_view,
    ai_conversation_state_view,
    ai_dimension_relationship_mapping_view,
    ai_dimension_view,
    ai_instance_dimension_view,
    ai_instance_memory_view,
    ai_instance_view,
    ai_message_buffer_view,
    ai_persona_view,
    ai_personality_placeholder_view,
    ai_personality_view,
    ai_relationship_view,
    ai_request_log_view,
    ai_style_dimension_view,
    ai_style_test_view,
    ai_style_view,
    ai_template_memory_view,
    ai_template_view,
    ai_type_view,
    chat_console_view,
    contact_request_view,
    contact_view,
    llm_config_test_view,
    llm_config_view,
    llm_provider_view,
    llm_test_log_view,
    login_record_view,
    media_file_view,
    message_delivery_view,
    message_device_view,
    message_dispatch_outbox_view,
    message_endpoint_view,
    message_history_view,
    notification_push_history_view,
    pending_contact_request_view,
    profile_view,
    square_type_entry_view,
    stats_ai_daily_view,
    stats_ai_monthly_view,
    stats_ai_weekly_view,
    stats_message_daily_view,
    stats_message_monthly_view,
    stats_message_weekly_view,
    stats_user_daily_view,
    stats_user_monthly_view,
    stats_user_weekly_view,
    system_config_view,
    user_auth_view,
    user_profile_log_view,
    user_risk_stats_view,
    user_token_view,
    user_view,
    user_violation_log_view,
)
from .views.ai_advanced_edit_views import (
    instance_advanced_edit_view,
    personality_advanced_edit_view,
    style_advanced_edit_view,
    template_advanced_edit_view,
)
from .views.dashboard_view import DashboardView
from .views.system_settings_view import SystemSettingsView

logger = logging.getLogger(__name__)


# Jinja2 filter helper for JSON rendering
def _pretty_json(data: Any) -> str:
    """Render JSON for admin templates without raising."""
    try:
        return json.dumps(data, default=str, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("admin_pretty_json_failed: %s", exc, exc_info=True)
        return str(data)


def _configure_template_env(admin_instance: Admin, settings: Settings) -> None:
    admin_instance.templates.env.filters["tojson"] = lambda data: json.dumps(
        data, default=str, ensure_ascii=False
    )
    admin_instance.templates.env.filters["admin_translate_labels"] = translate_labels
    admin_instance.templates.env.globals["settings"] = settings
    admin_instance.templates.env.globals["admin_text"] = admin_text
    try:
        admin_instance.templates.env.auto_reload = True
        cache = getattr(admin_instance.templates.env, "cache", None)
        if isinstance(cache, dict):
            cache.clear()
    except Exception as exc:
        logger.error("admin_template_env_config_failed: %s", exc, exc_info=True)
    admin_instance.templates.env.filters["prettyjson"] = _pretty_json


def _register_dropdowns(admin_instance: Admin) -> None:
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
    admin_instance.add_view(user_group)

    message_group = DropDown(
        "Messages",
        icon="fa fa-comments",
        views=[
            message_history_view,
            message_delivery_view,
            message_device_view,
            message_endpoint_view,
            message_dispatch_outbox_view,
            notification_push_history_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(message_group)

    ai_config_group = DropDown(
        "AI Configuration",
        icon="fa fa-sliders",
        views=[
            chat_console_view,
            pending_contact_request_view,
            ai_type_view,
            ai_persona_view,
            ai_template_view,
            ai_style_view,
            ai_personality_view,
            ai_relationship_view,
            ai_instance_view,
            ai_request_log_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(ai_config_group)

    ai_runtime_group = DropDown(
        "AI Runtime",
        icon="fa fa-robot",
        views=[
            ai_instance_memory_view,
            ai_instance_dimension_view,
            ai_message_buffer_view,
            ai_conversation_item_view,
            ai_conversation_item_archive_view,
            ai_conversation_runtime_view,
            ai_conversation_state_view,
            ai_dimension_view,
            ai_template_memory_view,
            ai_style_dimension_view,
            ai_personality_placeholder_view,
            ai_dimension_relationship_mapping_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(ai_runtime_group)

    admin_instance.add_view(ai_style_test_view)
    admin_instance.add_view(llm_config_test_view)

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
    admin_instance.add_view(llm_group)

    security_group = DropDown(
        "Security",
        icon="fa fa-shield",
        views=[
            user_risk_stats_view,
            user_violation_log_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(security_group)

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
    admin_instance.add_view(auth_group)

    media_group = DropDown(
        "Media",
        icon="fa fa-file-image",
        views=[
            media_file_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(media_group)

    app_content_group = DropDown(
        "App Content",
        icon="fa fa-mobile",
        views=[
            square_type_entry_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(app_content_group)

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
        ],
        always_open=False,
    )
    admin_instance.add_view(stats_group)

    system_group = DropDown(
        "System",
        icon="fa fa-cog",
        views=[
            SystemSettingsView(
                label="System Settings",
                icon="fa fa-cogs",
                path="/system-settings",
                methods=["GET", "POST"],
            ),
            system_config_view,
            admin_user_view,
            admin_operation_log_view,
            admin_login_log_view,
        ],
        always_open=False,
    )
    admin_instance.add_view(system_group)

    admin_instance.add_view(instance_advanced_edit_view)
    admin_instance.add_view(template_advanced_edit_view)
    admin_instance.add_view(personality_advanced_edit_view)
    admin_instance.add_view(style_advanced_edit_view)


class ThemeSwitchView(CustomView):
    """Lightweight view to switch admin theme (SSR)."""

    # Starlette Admin CustomView signature
    async def render(self, request: Request, _templates: Any) -> RedirectResponse:
        mode = str(request.path_params.get("mode", "light")).lower()
        if mode not in ("light", "dark", "auto"):
            mode = "light"
        admin_app = cast(Admin | None, getattr(self, "admin", None))
        if admin_app is None:
            raise RuntimeError("Admin application is not initialized")
        referer = request.headers.get("referer") or str(
            request.url_for(admin_app.route_name + ":index")
        )
        response = RedirectResponse(url=referer, status_code=303)
        response.set_cookie(
            "qiao_admin_theme",
            mode,
            max_age=60 * 60 * 24 * 365,
            path="/",
            samesite="lax",
        )
        return response


def _add_custom_views(admin_instance: Admin) -> None:
    theme_switch_view = ThemeSwitchView(
        label="Theme Switch",
        name="theme_switch",
        path="/theme/{mode:str}",
        add_to_menu=False,
    )
    admin_instance.add_view(theme_switch_view)


def _create_admin(settings: Settings) -> Admin:
    admin_instance = Admin(
        engine=get_engine(),
        title="Qiao Dashboard",
        base_url="/qiao-dash",
        debug=settings.DEBUG,
        i18n_config=build_i18n_config(),
        timezone_config=TimezoneConfig(
            default_timezone="Asia/Shanghai",
            timezone_cookie_name="timezone",
            database_timezone="UTC",
            use_user_locale_timezone=True,
        ),
        auth_provider=CustomAuthProvider(),
        templates_dir=str(Path(__file__).parent / "templates"),
        statics_dir=str(Path(__file__).parent / "static"),
        index_view=DashboardView(label="Dashboard", icon="fa fa-dashboard", path="/"),
    )
    _configure_template_env(admin_instance, settings)
    _register_dropdowns(admin_instance)
    _add_custom_views(admin_instance)
    return admin_instance


@lru_cache
def get_admin() -> Admin:
    """Return cached Admin application instance."""
    return _create_admin(get_settings())
