"""System settings views for non-database functionality.
All business logic is handled through internal API calls.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.config import get_settings
from app.crud.system import system_configs
from app.enums import AdminRole
from app.exceptions import MissingConfigurationError
from app.services.config import config_service
from app.services.media.config import (
    get_media_base_url,
    get_media_base_url_source,
    refresh_media_base_url,
)
from app.services.message.providers.leancloud.url_builder import (
    build_leancloud_webhook_url,
)
from app.services.storage.factory import reload_storage_backend
from app.services.system_config import SystemConfigService, get_config, get_configs_by_group
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SystemSettingsView(CustomView):
    """System settings management interface."""

    def is_active(self, request: Request) -> bool:
        """Check if current page is system settings by comparing full path including base_url."""
        path = request.scope["path"]
        # Get base_url from admin instance (e.g., "/qiao-dash")
        try:
            base_url = request.app.state.ADMIN.base_url
            full_path = base_url + self.path
            return path == full_path
        except AttributeError:
            # Fallback if base_url is not available
            return path.endswith(self.path)

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Render system settings interface."""
        try:
            # Get database session
            db = request.state.session

            config_groups = await get_configs_by_group(db)

            # Check for missing configs
            displayed_keys: set[str] = set()
            for group in config_groups.values():
                displayed_keys.update(group["configs"].keys())

            missing_configs = await SystemConfigService.check_missing_configs(db, displayed_keys)

            # Get webhook and LeanCloud IM data for System Management section
            webhook_token = await system_configs.get_config_value(
                db, config_key="leancloud_im_webhook_token"
            )
            api_base_url = await system_configs.get_config_value(db, config_key="api_base_url")
            conversation_id = await system_configs.get_config_value(
                db, config_key="leancloud_im_service_conversation_id"
            )

            # Get LeanCloud config
            leancloud_raw_config = await config_service.get_leancloud_config(db)
            leancloud_status = {
                "configured": bool(
                    leancloud_raw_config.get("app_id")
                    and leancloud_raw_config.get("master_key")
                    and leancloud_raw_config.get("base_url")
                ),
                "has_app_id": bool(leancloud_raw_config.get("app_id")),
                "has_master_key": bool(leancloud_raw_config.get("master_key")),
                "has_base_url": bool(leancloud_raw_config.get("base_url")),
            }

            # Construct webhook URL
            webhook_url = None
            if webhook_token and api_base_url:
                webhook_url = build_leancloud_webhook_url(
                    api_base_url=str(api_base_url),
                    webhook_token=str(webhook_token),
                )

            media_cdn_context = await self._get_media_cdn_context(db)

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
                "leancloud_config": leancloud_status,
                "media_cdn_config": media_cdn_context,
            }

            # Handle POST request (save settings)
            if request.method == "POST":
                form_data = await request.form()
                action = form_data.get("action")

                if action == "reload_media_cdn":
                    try:
                        await SystemConfigService.reload_cache(db)
                        await refresh_media_base_url(db)
                        reload_storage_backend()
                        context["success"] = "CDN configuration reloaded successfully."
                        logger.info("media_public_base_url_reloaded_manual")
                    except Exception as exc:
                        logger.error("media_cdn_reload_failed", error=str(exc), exc_info=True)
                        context["error"] = f"Failed to reload CDN configuration: {exc!s}"
                else:
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

                        if admin_role_val not in (AdminRole.ADMIN, AdminRole.SUPER_ADMIN):
                            context["error"] = "Permission denied"
                            return templates.TemplateResponse(
                                "custom_views/system_settings.html", context
                            )

                        if not admin_user_id:
                            context["error"] = "Admin user not found in session"
                            return templates.TemplateResponse(
                                "custom_views/system_settings.html", context
                            )

                        # Track changes for logging
                        changes = []

                        # Only process modification fields (config_modify_*)
                        media_config_updated = False

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
                                            if config_key == "media_public_base_url":
                                                media_config_updated = True
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

                            if media_config_updated:
                                await refresh_media_base_url(db)
                                reload_storage_backend()
                                logger.info("media_public_base_url_reloaded")

                            context["success"] = (
                                f"Successfully updated {len(changes)} configuration(s)"
                            )
                            logger.info(
                                "system_settings_updated",
                                count=len(changes),
                                admin_user_id=admin_user_id,
                            )
                        else:
                            context["warning"] = (
                                "No changes to save (all modification fields were empty)"
                            )

                    except Exception as e:
                        logger.error("system_settings_error", error=str(e), exc_info=True)
                        context["error"] = f"Failed to update settings: {e!s}"

                # Reload configurations to show updated values
                config_groups = await get_configs_by_group(db)
                context["config_groups"] = config_groups
                context["media_cdn_config"] = await self._get_media_cdn_context(db)

            return templates.TemplateResponse("custom_views/system_settings.html", context)

        except Exception as e:
            logger.error("system_settings_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
                "error": f"Failed to load settings: {e!s}",
                "success": None,
                "warning": None,
                "config_groups": {},
                "missing_configs": [],
                "webhook_url": None,
                "webhook_token": None,
                "token_length": 0,
                "conversation_id": None,
                "leancloud_config": {
                    "configured": False,
                    "has_app_id": False,
                    "has_master_key": False,
                    "has_base_url": False,
                },
                "media_cdn_config": {
                    "db_value": "",
                    "default_value": "",
                    "runtime_value": "",
                    "runtime_source": "unavailable",
                    "env_value": "",
                },
            }
            return templates.TemplateResponse("custom_views/system_settings.html", context)

    async def _get_media_cdn_context(self, db: AsyncSession) -> dict[str, str]:
        """Return CDN configuration state for templates."""
        settings = get_settings()
        config_row = await system_configs.get_by_key(db, config_key="media_public_base_url")
        db_value = config_row.config_value if config_row and config_row.config_value else ""
        default_value = config_row.default_value if config_row and config_row.default_value else ""
        env_value = settings.MEDIA_PUBLIC_BASE_URL or ""
        runtime_source = get_media_base_url_source()
        try:
            runtime_value = get_media_base_url()
        except MissingConfigurationError:
            runtime_value = ""
        return {
            "db_value": db_value,
            "default_value": default_value,
            "runtime_value": runtime_value,
            "runtime_source": runtime_source,
            "env_value": env_value,
        }
