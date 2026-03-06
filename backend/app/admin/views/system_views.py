"""System-related model views for Starlette-Admin.
Creates ModelView instances for user management and admin system models.
"""

from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin import DateTimeField, JSONField, StringField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField
from app.core.security import get_password_hash
from app.enums import AdminLoginResult, AdminRole, AdminStatus, ConfigType
from app.models.admin import AdminLoginLog, AdminOperationLog, AdminUser
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

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("config_key", False)]
    searchable_fields = ["config_key", "description"]
    sortable_fields = ["id", "config_key", "config_type", "created_at", "updated_at"]

    fields = [
        StringField("id", label="ID", help_text="Configuration ID"),
        StringField("config_key", label="Config Key", help_text="Unique configuration key"),
        StringField("config_value", label="Config Value", help_text="Configuration value"),
        StringField(
            "default_value",
            label="Default Value",
            help_text="Default configuration value",
        ),
        IntegerEnumField(
            "config_type",
            enum=ConfigType,
            label="Config Type",
            help_text="Data type of the configuration",
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

# Export all user and admin views
SYSTEM_MODEL_VIEWS = [
    system_config_view,
    admin_user_view,
    admin_operation_log_view,
    admin_login_log_view,
]
