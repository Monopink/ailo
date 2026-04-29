"""System-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin import DateTimeField, EnumField, IntegerField, JSONField, StringField
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
from app.models.system.runtime_observation import ClientRuntimeObservation

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

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Keep SystemConfigView unopinionated for config_value/default_value."""
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


class ClientRuntimeObservationView(ModelView):
    """Read-only runtime observation view for system troubleshooting."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("occurred_at", True)]
    searchable_fields = [
        "client_type",
        "device_id",
        "session_id",
        "event_name",
        "request_id",
        "entry_source",
    ]
    sortable_fields = [
        "id",
        "client_type",
        "device_id",
        "session_id",
        "user_id",
        "build_id",
        "event_name",
        "entry_source",
        "scope_snapshot",
        "network_type",
        "ua_fetch_status",
        "occurred_at",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Runtime observation ID"),
        StringField("client_type", label="Client Type", help_text="Client platform type"),
        StringField("device_id", label="Device ID", help_text="Client device identifier"),
        StringField(
            "session_id", label="Session ID", help_text="Client runtime session identifier"
        ),
        StringField("user_id", label="User ID", help_text="Bound user id when available"),
        StringField("user_agent", label="User Agent", help_text="Runtime user-agent snapshot"),
        StringField("event_name", label="Event Name", help_text="Runtime event name"),
        StringField("page_path", label="Page Path", help_text="Page path at event time"),
        StringField("entry_source", label="Entry Source", help_text="Entry source tag"),
        IntegerField("scope_snapshot", label="Scope Snapshot", help_text="0=standard, 1=limited"),
        JSONField("feature_hits", label="Feature Hits", help_text="Matched runtime feature names"),
        IntegerField("ua_fetch_status", label="UA Fetch Status", help_text="0~3"),
        JSONField("event_payload", label="Event Payload", help_text="Runtime event payload"),
        StringField(
            "event_payload_digest",
            label="Payload Digest",
            help_text="SHA256 digest of normalized payload",
        ),
        StringField("request_id", label="Request ID", help_text="Client request identifier"),
        StringField("platform", label="Platform", help_text="Runtime platform"),
        StringField("os_version", label="OS Version", help_text="Client OS version"),
        StringField("app_version", label="App Version", help_text="Client app version"),
        StringField("build_id", label="Build ID", help_text="Client build identifier"),
        DateTimeField("build_time", label="Build Time", help_text="Client build time (UTC)"),
        StringField(
            "network_type", label="Network Type", help_text="Network type at reporting time"
        ),
        DateTimeField("occurred_at", label="Occurred At", help_text="Client event time (UTC)"),
        DateTimeField("created_at", label="Created At", help_text="Server ingestion time (UTC)"),
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
client_runtime_observation_view = ClientRuntimeObservationView(
    ClientRuntimeObservation,
    name="Client Runtime Observations",
    icon="fa fa-signal",
    identity="client_runtime_observations",
)

# Export all user and admin views
SYSTEM_MODEL_VIEWS = [
    system_config_view,
    alert_event_view,
    alert_event_entity_view,
    client_runtime_observation_view,
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
]
