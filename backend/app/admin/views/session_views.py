"""
Session management related admin views.

This module contains Starlette-Admin views for managing user sessions and login records.
"""

from typing import Dict, Any
from starlette.requests import Request
from starlette_admin.contrib.sqla import ModelView
from starlette_admin import EnumField, StringField, IntegerField, DateTimeField, TextAreaField
from starlette_admin.exceptions import FormValidationError

# Import session models
from models.user import UserSession, LoginRecord

# Import enums
from enums import (
    DeviceType,
    LoginType,
    LoginResult,
    UserStatus,
)


class UserSessionView(ModelView):
    """Enhanced User Session view for session monitoring and management."""

    label = "User Sessions"
    name = "User Sessions"

    exclude_fields_from_create = ["id", "session_token", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "session_token", "created_at", "updated_at"]
    exclude_fields_from_list = ["platform_info", "user_agent"]

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
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal session ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        StringField("session_token", label="Session Token", help_text="Session authentication token"),
        EnumField(
            "device_type",
            enum=DeviceType,
            label="Device Type",
            help_text="Type of device used for login",
        ),
        StringField("device_id", label="Device ID", help_text="Unique device identifier"),
        "platform_info",
        StringField("ip_address", label="IP Address", help_text="Login IP address"),
        TextAreaField("user_agent", label="User Agent", help_text="Browser/device user agent"),
        DateTimeField("expires_at", label="Expires At", help_text="Session expiration time"),
        EnumField(
            "status",
            choices=[(1, "Active"), (0, "Inactive")],
            label="Status",
            help_text="Session status",
        ),
        DateTimeField("last_activity_at", label="Last Activity", help_text="Last activity timestamp"),
        DateTimeField("created_at", label="Created At", help_text="Session creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: Dict[str, Any]) -> None:
        """Custom validation for session management."""
        # Validate session status changes
        if "status" in data:
            status = data["status"]
            if status not in [0, 1]:
                raise FormValidationError({"status": "Invalid session status"})

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

    exclude_fields_from_list = ["user_agent", "fail_reason"]
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
        DateTimeField("login_time", label="Login Time", help_text="Time of login attempt"),
        EnumField(
            "login_type",
            enum=LoginType,
            label="Login Type",
            help_text="Method used for login",
        ),
        EnumField(
            "platform",
            enum=DeviceType,
            label="Platform",
            help_text="Platform used for login",
        ),
        StringField("device_id", label="Device ID", help_text="Device identifier"),
        StringField("ip_address", label="IP Address", help_text="Login IP address"),
        TextAreaField("user_agent", label="User Agent", help_text="Browser/device user agent"),
        EnumField(
            "result",
            enum=LoginResult,
            label="Result",
            help_text="Login attempt result",
        ),
        TextAreaField("fail_reason", label="Failure Reason", help_text="Reason for login failure"),
        StringField("session_token", label="Session Token", help_text="Associated session token"),
        DateTimeField("created_at", label="Created At", help_text="Record creation time"),
    ]


# Create view instances
user_session_view = UserSessionView(
    UserSession, name="User Sessions", icon="fa fa-desktop", identity="user_session"
)

login_record_view = LoginRecordView(
    LoginRecord, name="Login Records", icon="fa fa-sign-in-alt", identity="login_record"
)

# Export session views
SESSION_MODEL_VIEWS = [
    user_session_view,
    login_record_view,
]
