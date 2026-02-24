"""Security monitoring related admin views.

This module contains Starlette-Admin views for managing user security logs and statistics.
"""

from typing import Any

from starlette.requests import Request
from starlette_admin import DateTimeField, IntegerField, StringField, TextAreaField
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import FormValidationError

from app.admin.views.base import IntegerEnumField

# Import enums
from app.enums import (
    AutoAction,
    ManualReviewStatus,
    RiskLevel,
    SeverityLevel,
    ViolationType,
)

# Import security models
from app.models.security import UserRiskStats, UserViolationLog


class UserViolationLogView(ModelView):
    """Enhanced User Violation Log view for violation monitoring."""

    label = "Violation Logs"
    name = "Violation Logs"

    # Read-only view for security logs
    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    exclude_fields_from_list = []
    fields_default_sort = [("created_at", True)]
    searchable_fields = ["user_qiao_id", "instance_qiao_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "instance_qiao_id",
        "violation_type",
        "severity_level",
        "auto_action_taken",
        "manual_review_status",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal security log ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        StringField(
            "instance_id",
            label="Instance ID",
            help_text="AI instance snowflake ID (if applicable)",
        ),
        StringField(
            "instance_qiao_id",
            label="Instance Qiao ID",
            help_text="AI instance qiao ID",
        ),
        IntegerEnumField(
            "violation_type",
            enum=ViolationType,
            label="Violation Type",
            help_text="Type of security violation detected",
        ),
        IntegerEnumField(
            "severity_level",
            enum=SeverityLevel,
            label="Severity Level",
            help_text="Severity level of the violation",
        ),
        TextAreaField(
            "original_message",
            label="Original Message",
            help_text="User's original message",
        ),
        IntegerEnumField(
            "auto_action_taken",
            enum=AutoAction,
            label="Auto Action",
            help_text="Automatic action taken by system",
        ),
        IntegerEnumField(
            "manual_review_status",
            enum=ManualReviewStatus,
            label="Review Status",
            help_text="Manual review status",
        ),
        StringField(
            "reviewer_id",
            label="Reviewer ID",
            help_text="Admin snowflake ID who reviewed this record",
        ),
        TextAreaField("review_notes", label="Review Notes", help_text="Manual review notes"),
        DateTimeField("created_at", label="Created At", help_text="When violation was detected"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class UserRiskStatsView(ModelView):
    """Enhanced User Risk Stats view for risk assessment."""

    label = "User Risk Stats"
    name = "User Risk Stats"

    exclude_fields_from_create = ["id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_edit = ["id", "user_id", "created_at", "updated_at"]
    exclude_fields_from_list = []

    fields_default_sort = [("current_risk_level", True), ("total_violations", True)]
    searchable_fields = ["user_qiao_id"]
    sortable_fields = [
        "id",
        "user_qiao_id",
        "total_violations",
        "current_risk_level",
        "consecutive_violations",
        "warning_count",
        "restriction_count",
        "suspension_count",
        "last_violation_at",
        "last_action_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal security stats ID"),
        StringField("user_id", label="User ID", help_text="User snowflake ID"),
        StringField("user_qiao_id", label="User Qiao ID", help_text="User external identifier"),
        IntegerField(
            "total_violations",
            label="Total Violations",
            help_text="Total violation count",
        ),
        "violation_by_type",
        DateTimeField(
            "last_violation_at",
            label="Last Violation",
            help_text="Time of last violation",
        ),
        IntegerEnumField(
            "current_risk_level",
            enum=RiskLevel,
            label="Risk Level",
            help_text="Current user risk level",
        ),
        IntegerField(
            "consecutive_violations",
            label="Consecutive Violations",
            help_text="Consecutive violations (resets after 7 days)",
        ),
        IntegerField(
            "warning_count",
            label="Warning Count",
            help_text="Number of warnings issued",
        ),
        IntegerField(
            "restriction_count",
            label="Restriction Count",
            help_text="Number of restrictions applied",
        ),
        IntegerField(
            "suspension_count",
            label="Suspension Count",
            help_text="Number of suspensions applied",
        ),
        DateTimeField(
            "last_action_at",
            label="Last Action",
            help_text="Time of last administrative action",
        ),
        DateTimeField("created_at", label="Created At", help_text="Record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]

    async def validate(self, request: Request, data: dict[str, Any]) -> None:
        """Custom validation for security stats."""
        # Validate risk level changes
        if "current_risk_level" in data:
            risk_level = data["current_risk_level"]
            if risk_level not in [level.value for level in RiskLevel]:
                raise FormValidationError({"current_risk_level": "Invalid risk level"})

        return await super().validate(request, data)


# Create view instances
user_violation_log_view = UserViolationLogView(
    UserViolationLog,
    name="Violation Logs",
    icon="fa fa-exclamation-triangle",
    identity="user_violation_log",
)

user_risk_stats_view = UserRiskStatsView(
    UserRiskStats,
    name="User Risk Stats",
    icon="fa fa-shield",
    identity="user_risk_stats",
)

# Export security views
SECURITY_MODEL_VIEWS = [
    user_violation_log_view,
    user_risk_stats_view,
]
