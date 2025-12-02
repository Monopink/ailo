"""
Token management related admin views.

This module contains Starlette-Admin views for managing user tokens and login records.
"""

from typing import Any

from admin.fields import LocalDateTimeField
from admin.views.base import IntegerEnumField

# Import enums
from enums import AuthType, DeviceType, LoginResult, LoginType

# Import token models
from models.user import LoginRecord, UserAuth, UserToken
from starlette.requests import Request
from starlette_admin import StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError


class UserTokenView(ModelView):
    """Enhanced User Token view for token monitoring and management."""

    label = "User Tokens"
    name = "User Tokens"

    exclude_fields_from_create = ["id", "token", "created_at", "updated_at", "revoked_at"]
    exclude_fields_from_edit = ["id", "token", "created_at", "updated_at"]
    exclude_fields_from_list = ["token"]
    exclude_fields_from_detail = ["token"]

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("last_activity_at", True)]
    searchable_fields = ["user_qiao_id", "device_id", "ip_address"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "device_type",
        "status",
        "expires_at",
        "last_activity_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal token ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        StringField("token", label="JWT Token", help_text="JWT authentication token"),
        IntegerEnumField(
            "device_type",
            enum=DeviceType,
            label="Device Type",
            help_text="Type of device used for login",
        ),
        StringField("device_id", label="Device ID", help_text="Unique device identifier"),
        "platform_info",
        StringField("ip_address", label="IP Address", help_text="Login IP address"),
        TextAreaField("user_agent", label="User Agent", help_text="Browser/device user agent"),
        LocalDateTimeField("expires_at", label="Expires At", help_text="Token expiration time"),
        IntegerEnumField(
            "status",
            choices=[(1, "Active"), (2, "Revoked")],
            label="Status",
            help_text="Token status",
        ),
        LocalDateTimeField("revoked_at", label="Revoked At", help_text="Token revocation time"),
        LocalDateTimeField(
            "last_activity_at", label="Last Activity", help_text="Last activity timestamp"
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Token creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for token management."""
        # Validate token status changes
        if "status" in data:
            status = data["status"]
            if status not in [1, 2]:
                raise FormValidationError({"status": "Invalid token status"})

        return await super().validate(request, data)


class LoginRecordView(ModelView):
    """Enhanced Login Record view for login history monitoring."""

    label = "Login Records"
    name = "Login Records"

    # Read-only view for login records
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    exclude_fields_from_list = []
    fields_default_sort = [("login_time", True)]
    searchable_fields = ["user_qiao_id", "ip_address", "device_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "login_time",
        "login_type",
        "platform",
        "result",
        "created_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal login record ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        LocalDateTimeField("login_time", label="Login Time", help_text="Time of login attempt"),
        IntegerEnumField(
            "login_type",
            enum=LoginType,
            label="Login Type",
            help_text="Method used for login",
        ),
        IntegerEnumField(
            "platform",
            enum=DeviceType,
            label="Platform",
            help_text="Platform used for login",
        ),
        StringField("device_id", label="Device ID", help_text="Device identifier"),
        StringField("ip_address", label="IP Address", help_text="Login IP address"),
        TextAreaField("user_agent", label="User Agent", help_text="Browser/device user agent"),
        IntegerEnumField(
            "result",
            enum=LoginResult,
            label="Result",
            help_text="Login attempt result",
        ),
        TextAreaField("fail_reason", label="Failure Reason", help_text="Reason for login failure"),
        StringField("token", label="JWT Token", help_text="Associated JWT token"),
        LocalDateTimeField("created_at", label="Created At", help_text="Record creation time"),
    ]


# Create view instances
user_token_view = UserTokenView(
    UserToken, name="User Tokens", icon="fa fa-key", identity="user_token"
)

login_record_view = LoginRecordView(
    LoginRecord, name="Login Records", icon="fa fa-sign-in-alt", identity="login_record"
)

# Export token views
TOKEN_MODEL_VIEWS = [
    user_token_view,
    login_record_view,
]


class UserAuthView(ModelView):
    """User third-party identity bindings management."""

    label = "User Auths"
    name = "User Auths"

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("created_at", True)]
    searchable_fields = ["user_qiao_id", "provider_uid", "unionid", "app_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "auth_type",
        "status",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID"),
        StringField("user_id", label="User ID"),
        StringField("user_qiao_id", label="User Qiao ID"),
        IntegerEnumField("auth_type", enum=AuthType, label="Auth Type"),
        StringField("provider_uid", label="Provider UID"),
        StringField("unionid", label="UnionID"),
        StringField("app_id", label="App ID"),
        IntegerEnumField("status", choices=[(1, "Active"), (2, "Revoked")], label="Status"),
        TextAreaField("extra_data", label="Extra Data"),
        LocalDateTimeField("revoked_at", label="Revoked At"),
        LocalDateTimeField("created_at", label="Created At"),
        LocalDateTimeField("updated_at", label="Updated At"),
    ]


user_auth_view = UserAuthView(UserAuth, name="User Auths", icon="fa fa-link", identity="user_auth")

# Extend exported views to include user_auth
TOKEN_MODEL_VIEWS.append(user_auth_view)
