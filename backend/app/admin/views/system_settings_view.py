"""System settings views for non-database functionality.
All business logic is handled through internal API calls.
"""

import copy
from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.admin.i18n import (
    admin_config_description,
    admin_config_display_name,
    admin_config_group_title,
    admin_text,
)
from app.crud.system import system_configs
from app.enums import AdminRole, ConfigShape
from app.services.media.config import refresh_media_base_url
from app.services.message.providers.leancloud.config import get_leancloud_config_status
from app.services.message.providers.leancloud.url_builder import (
    build_leancloud_webhook_url,
)
from app.services.storage.factory import reload_storage_backend
from app.services.system_config import (
    SystemConfigService,
    get_config,
    get_configs_by_group_with_scope,
)
from app.services.system_settings_validation import validate_operation_config_updates
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SystemSettingsView(CustomView):
    """System settings management interface."""

    def __init__(
        self,
        *args: object,
        scopes: set[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._scopes = scopes if scopes is not None else {"system", "security"}

    def _is_operation_view(self) -> bool:
        return self._scopes == {"operation"}

    def _build_page_title(self) -> str:
        return "Operation Settings" if self._is_operation_view() else "System Settings"

    def _build_config_section_title(self) -> str:
        return "Operation Configuration" if self._is_operation_view() else "System Configuration"

    def _template_name(self) -> str:
        if self._is_operation_view():
            return "custom_views/system_settings/operation_page.html"
        return "custom_views/system_settings/system_page.html"

    @staticmethod
    def _can_write_invitation_policy(request: Request) -> bool:
        """Return whether current session has write permission for invitation policy card."""
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        if not isinstance(admin_user, dict):
            return False
        role_raw = admin_user.get("role")
        try:
            role_value = int(role_raw)
        except (TypeError, ValueError):
            return False
        return role_value in (int(AdminRole.SUPER_ADMIN), int(AdminRole.ADMIN))

    @staticmethod
    def _localize_config_groups(config_groups: dict[str, object]) -> None:
        for group_key, group in config_groups.items():
            if not isinstance(group, dict):
                continue
            group["title"] = admin_config_group_title(str(group_key))

            configs = group.get("configs")
            if not isinstance(configs, dict):
                continue

            for config_key, config in configs.items():
                config.display_name = admin_config_display_name(str(config_key))
                config.display_description = admin_config_description(
                    str(config_key), getattr(config, "description", None)
                )

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

            config_groups = await get_configs_by_group_with_scope(db, scopes=self._scopes)
            self._localize_config_groups(config_groups)
            editable_config_keys: set[str] = set()
            editable_configs: dict[str, Any] = {}
            for group in config_groups.values():
                for config_key, config in group["configs"].items():
                    editable_config_keys.add(config_key)
                    editable_configs[config_key] = config

            show_system_management = "operation" not in self._scopes
            webhook_url = None
            webhook_token = None
            conversation_id = None
            leancloud_status = {
                "configured": False,
                "has_app_id": False,
                "has_master_key": False,
                "has_base_url": False,
            }
            if show_system_management:
                webhook_token = await get_config(
                    db, key="leancloud_im_webhook_token", required=False
                )
                api_base_url = await get_config(db, key="api_base_url", required=False)
                conversation_id = await get_config(
                    db, key="leancloud_im_service_conversation_id", required=False
                )
                leancloud_status = await get_leancloud_config_status(db)
                if webhook_token and api_base_url:
                    webhook_url = build_leancloud_webhook_url(
                        api_base_url=str(api_base_url),
                        webhook_token=str(webhook_token),
                    )

            context = {
                "request": request,
                "success": None,
                "error": None,
                "warning": None,
                "config_groups": config_groups,
                "missing_configs": [],
                "page_title": self._build_page_title(),
                "show_system_management": show_system_management,
                "config_section_title": self._build_config_section_title(),
                "can_write_invitation_policy": self._can_write_invitation_policy(request),
                "webhook_url": webhook_url,
                "webhook_token": webhook_token,
                "token_length": len(webhook_token) if webhook_token else 0,
                "conversation_id": conversation_id,
                "leancloud_config": leancloud_status,
                "field_errors": {},
            }

            # Handle POST request (save settings)
            if request.method == "POST":
                form_data = await request.form()
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
                        context["error"] = admin_text("Permission denied")
                        return templates.TemplateResponse(self._template_name(), context)

                    if not admin_user_id:
                        context["error"] = admin_text("Admin user not found in session")
                        return templates.TemplateResponse(self._template_name(), context)

                    # Track changes for logging
                    changes = []
                    pending_updates: list[dict[str, object]] = []
                    review_validation_keys = (
                        "mp_weixin_review_deadline_at",
                        "mp_weixin_review_build_time_from",
                        "mp_weixin_review_build_time_to",
                        "mp_weixin_review_ip_blacklist",
                        "mp_weixin_release_build_ids",
                    )
                    persisted_review_values: dict[str, object] = {
                        config_key: copy.deepcopy(editable_configs[config_key].config_value)
                        for config_key in review_validation_keys
                        if config_key in editable_configs
                    }

                    # Only process modification fields (config_modify_*)
                    media_config_updated = False

                    for key, value in form_data.items():
                        if key.startswith("config_modify_"):
                            config_key = key[14:]  # Remove "config_modify_" prefix
                            if config_key not in editable_config_keys:
                                continue
                            config = editable_configs[config_key]

                            value_str = str(value).strip()
                            clear_flag = str(
                                form_data.get(f"config_clear_{config_key}", "")
                            ).strip()
                            should_clear = clear_flag == "1"
                            if not value_str and not should_clear:
                                continue

                            # Get old value from loaded config object to avoid
                            # hard-failing when optional keys are absent in DB.
                            old_value = copy.deepcopy(config.config_value)

                            target_value = value_str
                            validate_enum = True
                            allow_empty = False
                            new_value_log = value_str

                            if not value_str and should_clear:
                                config_shape = ConfigShape(int(config.config_shape))
                                target_value = "[]" if config_shape == ConfigShape.ARRAY else ""
                                validate_enum = False
                                allow_empty = True
                                new_value_log = "<cleared>"
                            elif (
                                ConfigShape(int(config.config_shape)) == ConfigShape.ARRAY
                                and value_str == "[]"
                            ):
                                allow_empty = True

                            pending_updates.append(
                                {
                                    "config_key": config_key,
                                    "target_value": target_value,
                                    "validate_enum": validate_enum,
                                    "allow_empty": allow_empty,
                                    "old_value": old_value,
                                    "new_value": new_value_log,
                                }
                            )

                    # Update config through CRUD layer (validates enum/value type)
                    for item in pending_updates:
                        config_key = str(item["config_key"])
                        try:
                            updated_config = await system_configs.update_config_value(
                                db,
                                config_key=config_key,
                                config_value=item["target_value"],
                                updated_by=admin_user_id,
                                validate_enum=bool(item["validate_enum"]),
                                allow_empty=bool(item["allow_empty"]),
                                commit=False,
                            )
                            if updated_config:
                                changes.append(
                                    {
                                        "config_key": config_key,
                                        "old_value": item["old_value"],
                                        "new_value": item["new_value"],
                                    }
                                )
                                if config_key == "media_public_base_url":
                                    media_config_updated = True
                        except (TypeError, ValueError) as ve:
                            await db.rollback()
                            context["error"] = str(ve)
                            context["field_errors"] = {
                                config_key: str(ve),
                            }
                            return templates.TemplateResponse(self._template_name(), context)

                    if pending_updates:
                        effective_review_values: dict[str, object] = {
                            config_key: copy.deepcopy(editable_configs[config_key].config_value)
                            for config_key in review_validation_keys
                            if config_key in editable_configs
                        }
                        validation_issues = validate_operation_config_updates(
                            effective_review_values,
                            persisted_values=persisted_review_values,
                        )
                        if validation_issues:
                            await db.rollback()
                            field_errors: dict[str, str] = {}
                            for issue in validation_issues:
                                existing_message = field_errors.get(issue.config_key)
                                if existing_message:
                                    field_errors[issue.config_key] = (
                                        f"{existing_message}；{issue.message}"
                                    )
                                else:
                                    field_errors[issue.config_key] = issue.message
                            context["error"] = admin_text(
                                "Failed to update settings: {error}"
                            ).format(error="审核配置校验失败")
                            context["field_errors"] = field_errors
                            return templates.TemplateResponse(self._template_name(), context)

                    if changes:
                        # Create operation logs for each change, then commit once with the config updates.
                        for change in changes:
                            resource_key = str(change["config_key"])
                            old_value = str(change["old_value"])
                            new_value = str(change["new_value"])
                            await create_operation_log(
                                db=db,
                                admin_user_id=admin_user_id,
                                operation_type=2,  # UPDATE
                                resource_type="system_config",
                                resource_id=resource_key,
                                resource_name=resource_key.replace("_", " ").title(),
                                operation_desc=f"Updated from '{old_value}' to '{new_value}'",
                                request=request,
                                commit=False,
                            )

                        await db.commit()

                        # Reload cache to sync changes to Service layer
                        await SystemConfigService.reload_cache(db)

                        if media_config_updated:
                            await refresh_media_base_url(db)
                            reload_storage_backend()
                            logger.info("media_public_base_url_reloaded")

                        context["success"] = admin_text(
                            "Successfully updated {count} configuration(s)"
                        ).format(count=len(changes))
                        logger.info(
                            "system_settings_updated",
                            count=len(changes),
                            admin_user_id=admin_user_id,
                        )
                    else:
                        context["warning"] = admin_text(
                            "No changes to save (all modification fields were empty)"
                        )

                except Exception as e:
                    await db.rollback()
                    logger.error("system_settings_error", error=str(e), exc_info=True)
                    context["error"] = admin_text("Failed to update settings: {error}").format(
                        error=f"{e!s}"
                    )

                # Reload configurations to show updated values
                config_groups = await get_configs_by_group_with_scope(db, scopes=self._scopes)
                self._localize_config_groups(config_groups)
                context["config_groups"] = config_groups
                if context["show_system_management"]:
                    webhook_token = await get_config(
                        db, key="leancloud_im_webhook_token", required=False
                    )
                    api_base_url = await get_config(db, key="api_base_url", required=False)
                    conversation_id = await get_config(
                        db, key="leancloud_im_service_conversation_id", required=False
                    )
                    leancloud_status = await get_leancloud_config_status(db)
                    webhook_url = None
                    if webhook_token and api_base_url:
                        webhook_url = build_leancloud_webhook_url(
                            api_base_url=str(api_base_url),
                            webhook_token=str(webhook_token),
                        )
                    context["webhook_url"] = webhook_url
                    context["webhook_token"] = webhook_token
                    context["token_length"] = len(webhook_token) if webhook_token else 0
                    context["conversation_id"] = conversation_id
                    context["leancloud_config"] = leancloud_status

            return templates.TemplateResponse(self._template_name(), context)

        except Exception as e:
            logger.error("system_settings_render_error", error=str(e), exc_info=True)
            context = {
                "request": request,
                "error": admin_text("Failed to load settings: {error}").format(error=f"{e!s}"),
                "success": None,
                "warning": None,
                "config_groups": {},
                "missing_configs": [],
                "page_title": self._build_page_title(),
                "show_system_management": "operation" not in self._scopes,
                "config_section_title": self._build_config_section_title(),
                "can_write_invitation_policy": self._can_write_invitation_policy(request),
                "webhook_url": None,
                "webhook_token": None,
                "token_length": 0,
                "conversation_id": None,
                "field_errors": {},
                "leancloud_config": {
                    "configured": False,
                    "has_app_id": False,
                    "has_master_key": False,
                    "has_base_url": False,
                },
            }
            return templates.TemplateResponse(self._template_name(), context)
