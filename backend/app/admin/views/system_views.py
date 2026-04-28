"""System-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

import json
from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin import DateTimeField, EnumField, JSONField, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField
from app.core.security import get_password_hash
from app.enums import (
    AdminLoginResult,
    AdminRole,
    AdminStatus,
    AlertSeverityLevel,
    ConfigShape,
    ConfigValueType,
    SystemConfigScope,
)
from app.models.admin import AdminLoginLog, AdminOperationLog, AdminUser
from app.models.system.alerting import AlertEvent, AlertEventEntity
from app.models.system.config import SystemConfig

from .base import BaseRoleAwareModelView


class _AdminUsernameField(StringField):
    """Computed field to display admin username by admin_user_id."""

    def __init__(self, name: str = "admin_username", label: str = "Admin Username") -> None:
        super().__init__(name=name, label=label)
        self.read_only = True
        self.searchable = False
        self.orderable = False

    async def parse_obj(self, request: Request, obj: Any) -> str:
        try:
            admin_user_id = getattr(obj, "admin_user_id", None)
            if not admin_user_id:
                return ""
            session = request.state.session
            result = await session.execute(
                select(AdminUser.username).where(AdminUser.id == admin_user_id)
            )
            value = result.scalar_one_or_none()
            return "" if value is None else str(value)
        except Exception:
            return ""


class SystemConfigView(ModelView):
    """Enhanced System Config view with proper field configuration."""

    exclude_fields_from_create = ["id", "created_at", "updated_at", "updated_by"]
    exclude_fields_from_edit = ["id", "created_at", "updated_at", "updated_by"]
    exclude_fields_from_list: list[str] = []
    exclude_fields_from_detail: list[str] = []

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "description"]
    sortable_fields = [
        "id",
        "config_key",
        "value_type",
        "config_shape",
        "config_scope",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Configuration ID"),
        StringField("config_key", label="Config Key", help_text="Unique configuration key"),
        JSONField("config_value", label="Config Value", help_text="Configuration value (JSONB)"),
        JSONField(
            "default_value",
            label="Default Value",
            help_text="Default configuration value",
        ),
        IntegerEnumField(
            "value_type",
            enum=ConfigValueType,
            label="Value Type",
            help_text="Data type of each value item",
        ),
        IntegerEnumField(
            "config_shape",
            enum=ConfigShape,
            label="Config Shape",
            help_text="Payload shape: single or array",
        ),
        EnumField(
            "config_scope",
            choices=[(item.value, item.value) for item in SystemConfigScope],
            label="Config Scope",
            help_text=f"Configuration scope ({', '.join([item.value for item in SystemConfigScope])})",
        ),
        StringField(
            "description",
            label="Description",
            help_text="Description of this configuration",
        ),
        StringField("group_name", label="Group Name", help_text="Configuration group name"),
        JSONField(
            "allowed_values",
            label="Allowed Values",
            help_text="Allowed values for enum type (JSON array)",
        ),
        StringField("updated_by", label="Updated By", help_text="Updater admin user ID"),
        DateTimeField("created_at", label="Created At", help_text="Configuration creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    @staticmethod
    def _parse_json_if_needed(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if raw == "":
            return value
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _normalize_single_value(  # noqa: PLR0911
        value_type: ConfigValueType,
        value: Any,
        field_name: str,
        *,
        allow_empty_string: bool = False,
    ) -> Any:
        if allow_empty_string and isinstance(value, str) and value.strip() == "":
            return ""

        if value_type == ConfigValueType.NUMBER:
            if isinstance(value, bool):
                raise TypeError(f"{field_name} must be integer.")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                if not value.is_integer():
                    raise ValueError(f"{field_name} must be integer.")
                return int(value)
            if isinstance(value, str):
                raw_value = value.strip()
                if raw_value == "":
                    raise ValueError(f"{field_name} must be integer.")
                try:
                    return int(raw_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{field_name} must be integer.") from exc
            raise TypeError(f"{field_name} must be integer.")

        if value_type == ConfigValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "on"}:
                    return True
                if lowered in {"false", "0", "no", "off"}:
                    return False
            raise ValueError(f"{field_name} must be boolean.")

        if value_type in {ConfigValueType.STRING, ConfigValueType.ENUM}:
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be string.")
            text = value.strip()
            if text == "":
                if allow_empty_string:
                    return ""
                raise ValueError(f"{field_name} must be non-empty string.")
            return text

        return value

    @classmethod
    def _normalize_value_by_shape(
        cls, *, value_type: ConfigValueType, config_shape: ConfigShape, value: Any, field_name: str
    ) -> Any:
        if config_shape == ConfigShape.SINGLE:
            return cls._normalize_single_value(value_type, value, field_name)

        if not isinstance(value, list):
            raise TypeError(f"{field_name} must be array when config_shape is ARRAY.")
        normalized_items: list[Any] = []
        for item in value:
            normalized_items.append(cls._normalize_single_value(value_type, item, field_name))
        if len(normalized_items) == 0:
            raise ValueError(f"{field_name} array cannot be empty.")
        return normalized_items

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Validate system config payload before create/edit."""
        value_type_raw = data.get("value_type")
        config_shape_raw = data.get("config_shape")
        if value_type_raw is not None and config_shape_raw is not None:
            value_type = ConfigValueType(int(value_type_raw))
            config_shape = ConfigShape(int(config_shape_raw))

            config_value = self._parse_json_if_needed(data.get("config_value"))
            default_value = self._parse_json_if_needed(data.get("default_value"))

            try:
                data["config_value"] = self._normalize_value_by_shape(
                    value_type=value_type,
                    config_shape=config_shape,
                    value=config_value,
                    field_name="config_value",
                )
            except (TypeError, ValueError) as exc:
                raise FormValidationError({"config_value": str(exc)}) from exc

            try:
                data["default_value"] = self._normalize_single_value(
                    value_type,
                    default_value,
                    "default_value",
                    allow_empty_string=True,
                )
            except (TypeError, ValueError) as exc:
                raise FormValidationError({"default_value": str(exc)}) from exc

        await super().validate(request, data)


class AdminUserView(BaseRoleAwareModelView):
    """Enhanced AdminUser view with proper field configuration."""

    def can_delete(self, request: Request) -> bool:
        return False

    def can_create(self, request: Request) -> bool:
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        role = admin_user.get("role") if admin_user else None
        try:
            role_val = int(role) if role is not None else None
        except Exception:
            role_val = None
        return role_val == AdminRole.SUPER_ADMIN

    def can_edit(self, request: Request) -> bool:
        admin_user = request.session.get("admin_user") if hasattr(request, "session") else None
        role = admin_user.get("role") if admin_user else None
        try:
            role_val = int(role) if role is not None else None
        except Exception:
            role_val = None
        return role_val == AdminRole.SUPER_ADMIN

    fields = [
        StringField("id", label="ID", help_text="Admin user ID"),
        StringField(
            "username",
            label="Username",
            help_text="Administrator username",
            required=True,
        ),
        StringField(
            "password",
            label="Password",
            help_text="Administrator password (plain text, leave blank to keep current password when editing)",
            required=False,
        ),
        IntegerEnumField(
            "role",
            enum=AdminRole,
            label="Role",
            help_text="Administrator role level (required selection: Super Admin, Admin, or Viewer)",
            required=True,
        ),
        IntegerEnumField(
            "status",
            enum=AdminStatus,
            label="Status",
            help_text="Account status (default: Active)",
            required=True,
        ),
        DateTimeField("last_login", label="Last Login", help_text="Last login time"),
        "login_count",
        "created_by",
        DateTimeField("created_at", label="Created At", help_text="Account creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username"]
    sortable_fields = [
        "id",
        "username",
        "role",
        "status",
        "created_at",
        "updated_at",
        "last_login",
    ]
    exclude_fields_from_list = ["password_hash", "password"]
    exclude_fields_from_detail = ["password_hash", "password"]
    exclude_fields_from_create = [
        "id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
        "login_count",
        "created_by",
    ]
    exclude_fields_from_edit = [
        "id",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login",
        "login_count",
        "created_by",
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Validate admin user data."""
        password = data.get("password")

        # For create operation, password is required
        if request.url.path.endswith("/create"):
            if not password:
                raise FormValidationError(
                    {"password": "Password is required when creating admin user"}
                )

        # Validate password length if provided
        min_password_length = 8
        if password and len(password) < min_password_length:
            raise FormValidationError({"password": "Password must be at least 8 characters long"})

        await super().validate(request, data)

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Hash password before creating admin user."""
        password = data.pop("password", None)

        if password:
            obj.password_hash = get_password_hash(password)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        """Hash password before updating admin user if password is changed."""
        password = data.pop("password", None)

        # Only update password if a new one is provided
        if password:
            obj.password_hash = get_password_hash(password)


class AdminOperationLogView(ModelView):
    """Enhanced Admin Operation Log view - read-only for monitoring."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["resource_name", "operation_desc"]
    sortable_fields = ["id", "admin_user_id", "resource_type", "created_at"]

    fields = [
        "id",
        "admin_user_id",
        _AdminUsernameField(),
        StringField("operation_type_display", label="Operation Type"),
        "resource_type",
        "resource_id",
        "resource_name",
        "operation_desc",
        JSONField("operation_meta", label="Operation Meta", required=False),
        "ip_address",
        "user_agent",
        DateTimeField("created_at", label="Created At", help_text="Operation time"),
    ]

    exclude_fields_from_create = ["operation_type_display"]
    exclude_fields_from_edit = ["operation_type_display"]


class AdminLoginLogView(ModelView):
    """Enhanced Admin Login Log view - read-only for monitoring."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["username", "ip_address"]
    sortable_fields = ["id", "admin_user_id", "username", "result", "created_at"]

    fields = [
        "id",
        "admin_user_id",
        _AdminUsernameField(),
        "username",
        IntegerEnumField(
            "result",
            enum=AdminLoginResult,
            label="Result",
            help_text="Login attempt result",
        ),
        "ip_address",
        "user_agent",
        DateTimeField("created_at", label="Created At", help_text="Login attempt time"),
    ]


class AlertEventView(ModelView):
    """Read-only alert event view for system-level monitoring."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["event_type", "domain", "dedupe_key"]
    sortable_fields = ["id", "event_type", "domain", "severity_level", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Alert event ID"),
        StringField("event_type", label="Event Type", help_text="Business alert event type"),
        StringField("domain", label="Domain", help_text="Business domain"),
        IntegerEnumField(
            "severity_level",
            enum=AlertSeverityLevel,
            label="Severity",
            help_text="Alert severity level",
        ),
        StringField("dedupe_key", label="Dedupe Key", help_text="Optional deduplication key"),
        JSONField("details", label="Details", help_text="Alert diagnostics payload"),
        DateTimeField("created_at", label="Created At", help_text="Event creation time"),
    ]


class AlertEventEntityView(ModelView):
    """Read-only alert-event entity mapping view."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["event_id", "entity_type", "entity_id"]
    sortable_fields = ["id", "event_id", "entity_type", "entity_id", "created_at"]

    fields = [
        StringField("id", label="ID", help_text="Alert event entity row ID"),
        StringField("event_id", label="Event ID", help_text="Related alert_events.id"),
        StringField("entity_type", label="Entity Type", help_text="Entity type"),
        StringField("entity_id", label="Entity ID", help_text="Entity ID"),
        DateTimeField("created_at", label="Created At", help_text="Reference creation time"),
    ]


# Create view instances
system_config_view = SystemConfigView(
    SystemConfig, name="System Config", icon="fa fa-cog", identity="system_configs"
)
admin_user_view = AdminUserView(
    AdminUser, name="Admin Users", icon="fa fa-users", identity="admin_user"
)
admin_operation_log_view = AdminOperationLogView(
    AdminOperationLog,
    name="Operation Logs",
    icon="fa fa-list",
    identity="admin_operation_log",
)
admin_login_log_view = AdminLoginLogView(
    AdminLoginLog, name="Login Logs", icon="fa fa-sign-in", identity="admin_login_log"
)
alert_event_view = AlertEventView(
    AlertEvent, name="Alert Events", icon="fa fa-bell", identity="alert_events"
)
alert_event_entity_view = AlertEventEntityView(
    AlertEventEntity,
    name="Alert Event Entities",
    icon="fa fa-link",
    identity="alert_event_entities",
)

# Export all user and admin views
SYSTEM_MODEL_VIEWS = [
    system_config_view,
    alert_event_view,
    alert_event_entity_view,
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
]
