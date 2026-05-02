"""Security monitoring related admin views.

This module contains Starlette-Admin views for managing user security logs and statistics.
"""

from typing import Any

from starlette.requests import Request
from starlette_admin import DateTimeField, IntegerField, JSONField, StringField, TextAreaField
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
from app.models.security import (
    SecurityIPBlock,
    SecurityIPRiskStats,
    UserRiskStats,
    UserViolationLog,
)


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
        StringField("rule_code", label="Rule Code", help_text="Matched rule code"),
        StringField("rule_version", label="Rule Version", help_text="Matched rule version"),
        IntegerField(
            "detection_source",
            label="Detection Source",
            help_text="Security detection source enum value",
        ),
        StringField("http_method", label="HTTP Method", help_text="Triggering request method"),
        StringField("request_path", label="Request Path", help_text="Triggering request path"),
        StringField("client_ip", label="Client IP", help_text="Client source IP"),
        StringField("request_id", label="Request ID", help_text="Request trace identifier"),
        JSONField("evidence_payload", label="Evidence Payload", help_text="Attack evidence JSON"),
        IntegerField(
            "trigger_score",
            label="Trigger Score",
            help_text="Numeric score used for trigger classification",
        ),
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

    def can_delete(self, request: Request) -> bool:
        return False

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
        JSONField(
            "violation_by_type",
            label="Violation By Type",
            help_text="Aggregated violation counters by type",
        ),
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
        IntegerField(
            "high_risk_hits",
            label="High Risk Hits",
            help_text="High-risk event hit count",
        ),
        DateTimeField(
            "last_high_risk_at",
            label="Last High Risk",
            help_text="Time of last high-risk hit",
        ),
        DateTimeField(
            "last_suspend_at",
            label="Last Suspend",
            help_text="Time of last automatic suspension",
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


class SecurityIPRiskStatsView(ModelView):
    """IP risk aggregation view."""

    label = "IP Risk Stats"
    name = "IP Risk Stats"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("total_attack_count", True), ("last_attack_at", True)]
    searchable_fields = ["ip_address", "last_rule_code", "last_source"]
    sortable_fields = [
        "id",
        "ip_address",
        "high_risk_count_5m",
        "medium_risk_count_10m",
        "total_attack_count",
        "last_attack_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal IP risk stats ID"),
        StringField("ip_address", label="IP Address", help_text="Client source IP"),
        IntegerField(
            "high_risk_count_5m",
            label="High Risk Count (5m)",
            help_text="High-risk hit count within rolling 5-minute window",
        ),
        IntegerField(
            "medium_risk_count_10m",
            label="Medium Risk Count (10m)",
            help_text="Medium-risk hit count within rolling 10-minute window",
        ),
        IntegerField(
            "total_attack_count",
            label="Total Attack Count",
            help_text="Total recorded attack count",
        ),
        DateTimeField("last_attack_at", label="Last Attack At", help_text="Time of last hit"),
        StringField("last_rule_code", label="Last Rule Code", help_text="Last matched rule code"),
        StringField("last_source", label="Last Source", help_text="Last detection source"),
        StringField(
            "last_request_path",
            label="Last Request Path",
            help_text="Last triggering request path",
        ),
        StringField("last_user_id", label="Last User ID", help_text="Last resolved user ID"),
        DateTimeField("created_at", label="Created At", help_text="Record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


class SecurityIPBlockView(ModelView):
    """TTL-based IP block view."""

    label = "IP Blocks"
    name = "IP Blocks"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    fields_default_sort = [("blocked_at", True), ("expires_at", True)]
    searchable_fields = ["ip_address", "rule_code", "reason_code", "source"]
    sortable_fields = [
        "id",
        "ip_address",
        "severity_level",
        "status",
        "blocked_at",
        "expires_at",
        "created_at",
        "updated_at",
    ]

    fields = [
        StringField("id", label="ID", help_text="Internal IP block ID"),
        StringField("ip_address", label="IP Address", help_text="Blocked IP or CIDR base"),
        IntegerField("block_scope", label="Block Scope", help_text="Block scope enum value"),
        IntegerField(
            "cidr_prefix",
            label="CIDR Prefix",
            help_text="CIDR prefix length when block scope is CIDR",
        ),
        IntegerField("severity_level", label="Severity Level", help_text="Severity level"),
        StringField("reason_code", label="Reason Code", help_text="Penalty reason code"),
        StringField("rule_code", label="Rule Code", help_text="Matched rule code"),
        StringField("rule_version", label="Rule Version", help_text="Matched rule version"),
        StringField("source", label="Source", help_text="Detection source label"),
        StringField(
            "request_path",
            label="Request Path",
            help_text="Request path at blocking time",
        ),
        StringField(
            "request_method",
            label="Request Method",
            help_text="HTTP method at blocking time",
        ),
        JSONField(
            "evidence_payload",
            label="Evidence Payload",
            help_text="Structured evidence payload",
        ),
        IntegerField("hit_count", label="Hit Count", help_text="Merged hit count"),
        DateTimeField("first_hit_at", label="First Hit At", help_text="First hit time"),
        DateTimeField("blocked_at", label="Blocked At", help_text="Block start time"),
        DateTimeField("expires_at", label="Expires At", help_text="Block expiry time"),
        IntegerField("status", label="Status", help_text="Block status enum value"),
        DateTimeField("released_at", label="Released At", help_text="Release timestamp"),
        StringField("release_reason", label="Release Reason", help_text="Release reason"),
        DateTimeField("created_at", label="Created At", help_text="Record creation time"),
        DateTimeField("updated_at", label="Updated At", help_text="Last update time"),
    ]


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

security_ip_risk_stats_view = SecurityIPRiskStatsView(
    SecurityIPRiskStats,
    name="IP Risk Stats",
    icon="fa fa-network-wired",
    identity="security_ip_risk_stats",
)

security_ip_block_view = SecurityIPBlockView(
    SecurityIPBlock,
    name="IP Blocks",
    icon="fa fa-ban",
    identity="security_ip_blocks",
)

# Export security views
SECURITY_MODEL_VIEWS = [
    user_violation_log_view,
    user_risk_stats_view,
    security_ip_risk_stats_view,
    security_ip_block_view,
]
