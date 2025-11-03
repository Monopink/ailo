"""
Custom views for non-database functionality.
All business logic is handled through internal API calls.
"""

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from utils.logging import get_logger

logger = get_logger(__name__)


class DashboardView(CustomView):
    """Dashboard with system overview."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render dashboard page with initial data from database."""
        try:
            # Get database session
            db = request.state.session

            from crud.system import system_configs
            from services.config import config_service
            from services.message.health import get_message_service_status

            # Read initial data from database
            webhook_token = await system_configs.get_config_value(db, config_key="leancloud_webhook_token")
            api_base_url = await system_configs.get_config_value(db, config_key="api_base_url")
            conversation_id = await system_configs.get_config_value(
                db, config_key="leancloud_service_conversation_id"
            )

            # Get LeanCloud config
            leancloud_config = await config_service.get_leancloud_config(db)

            # Check message service health
            health_status = await get_message_service_status(db)

            # Construct webhook URL
            webhook_url = None
            if webhook_token and api_base_url:
                webhook_url = f"{api_base_url}/api/v1/webhook/leancloud/{webhook_token}"

            context = {
                "request": request,
                "webhook_url": webhook_url,
                "webhook_token": webhook_token,
                "token_length": len(webhook_token) if webhook_token else 0,
                "conversation_id": conversation_id,
                "leancloud_config": {
                    "configured": bool(
                        leancloud_config.get("app_id")
                        and leancloud_config.get("master_key")
                        and leancloud_config.get("base_url")
                    ),
                    "has_app_id": bool(leancloud_config.get("app_id")),
                    "has_master_key": bool(leancloud_config.get("master_key")),
                    "has_base_url": bool(leancloud_config.get("base_url")),
                },
                "message_service_health": health_status,
            }
            return templates.TemplateResponse("custom_views/dashboard.html", context)
        except Exception as e:
            logger.error("dashboard_render_error", error=str(e), exc_info=True)
            context = {"request": request}
            return templates.TemplateResponse("custom_views/dashboard.html", context)


class SystemSettingsView(CustomView):
    """System settings management interface."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render system settings interface."""

        try:
            # Get database session
            db = request.state.session

            # Get grouped configurations from service
            from services.system_config import get_configs_by_group, get_config, SystemConfigService
            from crud.system import system_configs
            from services.config import config_service
            from utils.admin_logs import create_operation_log

            config_groups = await get_configs_by_group(db)

            # Check for missing configs
            displayed_keys = set()
            for group in config_groups.values():
                displayed_keys.update(group["configs"].keys())

            missing_configs = await SystemConfigService.check_missing_configs(db, displayed_keys)

            # Get webhook and LeanCloud data for System Management section
            webhook_token = await system_configs.get_config_value(db, config_key="leancloud_webhook_token")
            api_base_url = await system_configs.get_config_value(db, config_key="api_base_url")
            conversation_id = await system_configs.get_config_value(
                db, config_key="leancloud_service_conversation_id"
            )

            # Get LeanCloud config
            leancloud_config = await config_service.get_leancloud_config(db)

            # Construct webhook URL
            webhook_url = None
            if webhook_token and api_base_url:
                webhook_url = f"{api_base_url}/api/v1/webhook/leancloud/{webhook_token}"

            context = {
                "request": request,
                "success": None,
                "error": None,
                "warning": None,
                "config_groups": config_groups,
                "missing_configs": missing_configs,
                "webhook_url": webhook_url,
                "webhook_token": webhook_token,
                "token_length": len(webhook_token) if webhook_token else 0,
                "conversation_id": conversation_id,
                "leancloud_config": {
                    "configured": bool(
                        leancloud_config.get("app_id")
                        and leancloud_config.get("master_key")
                        and leancloud_config.get("base_url")
                    ),
                    "has_app_id": bool(leancloud_config.get("app_id")),
                    "has_master_key": bool(leancloud_config.get("master_key")),
                    "has_base_url": bool(leancloud_config.get("base_url")),
                },
            }

            # Handle POST request (save settings)
            if request.method == "POST":
                try:
                    # Get admin user from session
                    admin_user = request.session.get("admin_user")
                    admin_user_id = admin_user.get("id") if admin_user else None
                    admin_role = admin_user.get("role") if admin_user else None

                    # Role check: only ADMIN and SUPER_ADMIN can modify settings
                    try:
                        admin_role_val = int(admin_role) if admin_role is not None else None
                    except Exception:
                        admin_role_val = None

                    from enums import AdminRole

                    if admin_role_val not in (AdminRole.ADMIN, AdminRole.SUPER_ADMIN):
                        context["error"] = "Permission denied"
                        return templates.TemplateResponse("custom_views/system_settings.html", context)

                    if not admin_user_id:
                        context["error"] = "Admin user not found in session"
                        return templates.TemplateResponse("custom_views/system_settings.html", context)

                    form_data = await request.form()

                    # Track changes for logging
                    changes = []

                    # Only process modification fields (config_modify_*)
                    for key, value in form_data.items():
                        if key.startswith("config_modify_"):
                            config_key = key[14:]  # Remove "config_modify_" prefix

                            # Only update if modification value is not empty
                            value_str = str(value).strip()
                            if value_str:
                                # Get old value for logging
                                old_value = await get_config(db, config_key)

                                # Update config through CRUD layer (validates enum)
                                try:
                                    config = await system_configs.update_config_value(
                                        db,
                                        config_key=config_key,
                                        config_value=value_str,
                                        updated_by=admin_user_id,
                                        validate_enum=True,
                                    )

                                    if config:
                                        changes.append(
                                            {
                                                "config_key": config_key,
                                                "old_value": old_value,
                                                "new_value": value_str,
                                            }
                                        )
                                except ValueError as ve:
                                    # Enum validation failed
                                    context["error"] = str(ve)
                                    return templates.TemplateResponse(
                                        "custom_views/system_settings.html", context
                                    )

                    # Create operation logs for each change
                    for change in changes:
                        await create_operation_log(
                            db=db,
                            admin_user_id=admin_user_id,
                            operation_type=2,  # UPDATE
                            resource_type="system_config",
                            resource_id=change["config_key"],
                            resource_name=change["config_key"].replace("_", " ").title(),
                            operation_desc=f"Updated from '{change['old_value']}' to '{change['new_value']}'",
                            request=request,
                        )

                    if changes:
                        # Reload cache to sync changes to Service layer
                        await SystemConfigService.reload_cache(db)

                        context["success"] = f"Successfully updated {len(changes)} configuration(s)"
                        logger.info(
                            "system_settings_updated", count=len(changes), admin_user_id=admin_user_id
                        )
                    else:
                        context["warning"] = "No changes to save (all modification fields were empty)"

                    # Reload configurations to show updated values
                    config_groups = await get_configs_by_group(db)
                    context["config_groups"] = config_groups

                except Exception as e:
                    logger.error("system_settings_error", error=str(e), exc_info=True)
                    context["error"] = f"Failed to update settings: {str(e)}"

            return templates.TemplateResponse("custom_views/system_settings.html", context)

        except Exception as e:
            logger.error("system_settings_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
                "error": f"Failed to load settings: {str(e)}",
                "config_groups": {},
                "missing_configs": [],
            }
            return templates.TemplateResponse("custom_views/system_settings.html", context)
