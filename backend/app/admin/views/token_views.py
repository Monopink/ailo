"""
Token management related admin views.

This module contains Starlette-Admin views for managing user tokens and login records.
"""

from typing import Any, ClassVar

from starlette.requests import Request
from starlette_admin import HasOne, JSONField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import BaseField

from app.admin.fields import LocalDateTimeField
from app.admin.views.base import IntegerEnumField

# Import enums
from app.enums import AuthType, DeviceType, LoginResult, LoginType

# Import token models
from app.models.user import LoginRecord, UserAuth, UserToken


class UserTokenView(ModelView):
    """Enhanced User Token view for token monitoring and management."""

    label = "User Tokens"
    name = "User Tokens"

    # Disable create - tokens should only be created through login API
    def can_create(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # Exclude auto-filled and sensitive fields from edit
    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "user_id",
        "user_qiao_id",
        "access_token",
        "device_type",
        "device_id",
        "platform_info",
        "ip_address",
        "user_agent",
        "access_expires_at",
        "last_activity_at",
        "access_revoked_at",
        "refresh_token_hash",
        "refresh_expires_at",
        "refresh_revoked_at",
        "token_metadata",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "user_id",
        "user_qiao_id",
        "access_token",
        "device_type",
        "device_id",
        "platform_info",
        "ip_address",
        "user_agent",
        "access_expires_at",
        "last_activity_at",
        "refresh_token_hash",
        "refresh_expires_at",
        "token_metadata",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_list: ClassVar[list[str]] = [
        "user_id",
        "user_qiao_id",
        "access_token",
        "refresh_token_hash",
        "token_metadata",
    ]
    exclude_fields_from_detail: ClassVar[list[str]] = ["access_token", "refresh_token_hash"]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("last_activity_at", True)]
    searchable_fields: ClassVar[list[str]] = ["user_qiao_id", "device_id", "ip_address"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "user_qiao_id",
        "device_type",
        "status",
        "access_expires_at",
        "last_activity_at",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[BaseField]] = [
        StringField("id", label="ID", help_text="Internal token ID"),
        HasOne(
            "user",
            identity="user",
            label="User",
            help_text="Associated user account",
            required=False,
        ),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        StringField("access_token", label="Access Token", help_text="JWT access token (sensitive)"),
        IntegerEnumField(
            "device_type",
            enum=DeviceType,
            label="Device Type",
            help_text="Type of device used for login",
        ),
        StringField("device_id", label="Device ID", help_text="Unique device identifier"),
        JSONField("platform_info", label="Platform Info", help_text="Platform information (JSONB)"),
        StringField("ip_address", label="IP Address", help_text="Login IP address"),
        TextAreaField("user_agent", label="User Agent", help_text="Browser/device user agent"),
        LocalDateTimeField(
            "access_expires_at", label="Access Expires At", help_text="Access token expiration time"
        ),
        IntegerEnumField(
            "status",
            choices=[(1, "Active"), (2, "Revoked")],
            label="Status",
            help_text="Token status (editable for revocation)",
        ),
        LocalDateTimeField(
            "access_revoked_at", label="Access Revoked At", help_text="Access token revocation time"
        ),
        StringField(
            "refresh_token_hash",
            label="Refresh Token Hash",
            help_text="Refresh token hash (sensitive)",
        ),
        LocalDateTimeField(
            "refresh_expires_at",
            label="Refresh Expires At",
            help_text="Refresh token expiration time",
        ),
        LocalDateTimeField(
            "refresh_revoked_at",
            label="Refresh Revoked At",
            help_text="Refresh token revocation time (editable)",
        ),
        JSONField(
            "token_metadata",
            label="Token Metadata",
            help_text="Additional metadata (refresh counters, etc.)",
        ),
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

    # Read-only view for login records (audit log)
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    exclude_fields_from_list: ClassVar[list[str]] = ["user_id", "user_qiao_id"]
    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("login_time", True)]
    searchable_fields: ClassVar[list[str]] = ["user_qiao_id", "ip_address", "device_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "user_qiao_id",
        "login_time",
        "login_type",
        "platform",
        "result",
        "created_at",
    ]

    fields: ClassVar[list[BaseField]] = [
        StringField("id", label="ID", help_text="Internal login record ID"),
        HasOne(
            "user",
            identity="user",
            label="User",
            help_text="Associated user account",
            required=False,
        ),
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

    # Disable create - third-party bindings should only be created through API
    def can_create(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # Exclude auto-filled and identity fields from edit
    exclude_fields_from_create: ClassVar[list[str]] = [
        "id",
        "user_id",
        "user_qiao_id",
        "auth_type",
        "provider_uid",
        "unionid",
        "app_id",
        "extra_data",
        "revoked_at",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_edit: ClassVar[list[str]] = [
        "id",
        "user_id",
        "user_qiao_id",
        "auth_type",
        "provider_uid",
        "unionid",
        "app_id",
        "extra_data",
        "created_at",
        "updated_at",
    ]

    exclude_fields_from_list: ClassVar[list[str]] = ["user_id", "user_qiao_id"]

    fields_default_sort: ClassVar[list[tuple[str, bool]]] = [("created_at", True)]
    searchable_fields: ClassVar[list[str]] = ["user_qiao_id", "provider_uid", "unionid", "app_id"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "user_qiao_id",
        "auth_type",
        "status",
        "created_at",
        "updated_at",
    ]

    fields: ClassVar[list[BaseField]] = [
        StringField("id", label="ID", help_text="Internal auth record ID"),
        HasOne(
            "user",
            identity="user",
            label="User",
            help_text="Associated user account",
            required=False,
        ),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        IntegerEnumField(
            "auth_type", enum=AuthType, label="Auth Type", help_text="Third-party platform type"
        ),
        StringField(
            "provider_uid", label="Provider UID", help_text="Platform user unique ID (openid/sub)"
        ),
        StringField("unionid", label="UnionID", help_text="WeChat unionid (optional)"),
        StringField("app_id", label="App ID", help_text="Platform app identifier"),
        IntegerEnumField(
            "status",
            choices=[(1, "Active"), (2, "Revoked")],
            label="Status",
            help_text="Binding status (editable for unbinding)",
        ),
        TextAreaField("extra_data", label="Extra Data", help_text="Additional information (JSONB)"),
        LocalDateTimeField(
            "revoked_at", label="Revoked At", help_text="Unbind time (auto-filled on revoke)"
        ),
        LocalDateTimeField("created_at", label="Created At", help_text="Binding creation time"),
        LocalDateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


user_auth_view = UserAuthView(UserAuth, name="User Auths", icon="fa fa-link", identity="user_auth")

# Extend exported views to include user_auth
TOKEN_MODEL_VIEWS.append(user_auth_view)
