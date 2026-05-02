"""Security monitoring related models.

This module contains SQLAlchemy models for user security logs and statistics.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import AutoAction, IPBlockScope, IPBlockStatus, ManualReviewStatus, RiskLevel
from app.models.base import SnowflakeModel
from app.type_defs import JSONDict


class UserViolationLog(SnowflakeModel):
    """User violation log model.

    User security violation records.
    """

    __tablename__ = "user_violation_logs"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="User ID, references users.id when available"
    )

    user_qiao_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="User external ID when available"
    )

    instance_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Instance ID if violation relates to a specific AI"
    )

    instance_qiao_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Instance external qiao_id"
    )

    violation_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=(
            "Violation type: 1=prompt_injection, 2=sql_injection, 3=command_injection, "
            "4=path_traversal, 99=other"
        ),
    )

    severity_level: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Severity: 1=low, 2=medium, 3=high, 4=critical"
    )

    original_message: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Original user message"
    )

    auto_action_taken: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=AutoAction.NONE,
        server_default=text("1"),
        comment="Auto action: 1=none, 2=warning, 3=restrict, 4=suspend",
    )

    manual_review_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ManualReviewStatus.PENDING,
        server_default=text("1"),
        comment="Manual review: 1=pending, 2=confirmed, 3=false_positive, 4=ignored",
    )

    reviewer_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Reviewer admin ID"
    )

    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Review notes")

    rule_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Matched attack rule code"
    )

    rule_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Matched attack rule version"
    )

    detection_source: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Detection source: 1=ai, 2=api_runtime, 3=api_auth, "
            "4=api_public_invitation, 5=nginx, 6=middleware"
        ),
    )

    http_method: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="HTTP method of the triggering request"
    )

    request_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Request path of the triggering request"
    )

    client_ip: Mapped[str | None] = mapped_column(
        INET, nullable=True, comment="Client source IP (raw value)"
    )

    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Request ID for traceability"
    )

    evidence_payload: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Structured evidence payload for attack decision",
    )

    trigger_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Numeric trigger score for rule hit"
    )


class UserRiskStats(SnowflakeModel):
    """User risk stats model.

    User security statistics summary.
    """

    __tablename__ = "user_risk_stats"

    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, comment="User ID, references users.id"
    )

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="User external ID"
    )

    total_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Total violation count",
    )

    violation_by_type: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment=(
            'Violations by type: {"prompt_injection": 5, "sql_injection": 2} '
            "(JSONB for better performance)"
        ),
    )

    last_violation_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last violation time"
    )

    current_risk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=RiskLevel.LOW,
        server_default=text("1"),
        comment="Risk level: 1=low, 2=medium, 3=high, 4=banned",
    )

    consecutive_violations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Consecutive violations (reset after 7 days)",
    )

    warning_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Warning count"
    )

    restriction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Restriction count"
    )

    suspension_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Suspension count"
    )

    last_action_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last action time"
    )

    high_risk_hits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="High-risk event hit count",
    )

    last_high_risk_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last high-risk hit time"
    )

    last_suspend_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last automatic suspend time"
    )


class SecurityIPRiskStats(SnowflakeModel):
    """IP-level risk aggregation for attack counting and threshold evaluation."""

    __tablename__ = "security_ip_risk_stats"

    ip_address: Mapped[str] = mapped_column(INET, nullable=False, comment="Client source IP")

    high_risk_count_5m: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="High-risk hit count within rolling 5-minute window",
    )

    medium_risk_count_10m: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Medium-risk hit count within rolling 10-minute window",
    )

    total_attack_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Total recorded attack count for this IP",
    )

    last_attack_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Last attack hit time"
    )

    last_rule_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Last matched rule code"
    )

    last_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Last detection source label"
    )

    last_request_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Last request path"
    )

    last_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Last resolved user ID when available"
    )

    __table_args__ = (
        CheckConstraint("high_risk_count_5m >= 0", name="ck_security_ip_risk_stats_high_5m_nonneg"),
        CheckConstraint(
            "medium_risk_count_10m >= 0", name="ck_security_ip_risk_stats_medium_10m_nonneg"
        ),
        CheckConstraint("total_attack_count >= 0", name="ck_security_ip_risk_stats_total_nonneg"),
        Index("uq_security_ip_risk_stats_ip", "ip_address", unique=True),
        Index("idx_security_ip_risk_stats_last_attack", "last_attack_at"),
    )


class SecurityIPBlock(SnowflakeModel):
    """TTL-based IP block records."""

    __tablename__ = "security_ip_blocks"

    ip_address: Mapped[str] = mapped_column(INET, nullable=False, comment="Blocked IP or CIDR base")

    block_scope: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=IPBlockScope.SINGLE_IP,
        server_default=text("1"),
        comment="Block scope: 1=single_ip, 2=cidr",
    )

    cidr_prefix: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="CIDR prefix length when block_scope=2"
    )

    severity_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Severity level: 1=low, 2=medium, 3=high, 4=critical"
    )

    reason_code: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Penalty reason code"
    )

    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="Rule code")

    rule_version: Mapped[str] = mapped_column(String(32), nullable=False, comment="Rule version")

    source: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Detection source label (nginx/backend)"
    )

    request_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Request path at blocking time"
    )

    request_method: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="HTTP method at blocking time"
    )

    evidence_payload: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Structured evidence payload for the block decision",
    )

    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Total hits merged into this active block record",
    )

    first_hit_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="First hit time in this block cycle"
    )

    blocked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Block start time"
    )

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Block expiry time"
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=IPBlockStatus.ACTIVE,
        server_default=text("1"),
        comment="Block status: 1=active, 2=released, 3=expired",
    )

    released_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, comment="Release timestamp"
    )

    release_reason: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="Release reason"
    )

    __table_args__ = (
        CheckConstraint(
            "expires_at > blocked_at",
            name="ck_security_ip_blocks_expiry_after_blocked",
        ),
        CheckConstraint("status IN (1, 2, 3)", name="ck_security_ip_blocks_status"),
        CheckConstraint("block_scope IN (1, 2)", name="ck_security_ip_blocks_scope"),
        CheckConstraint("severity_level IN (1, 2, 3, 4)", name="ck_security_ip_blocks_severity"),
        CheckConstraint(
            "(block_scope = 1 AND cidr_prefix IS NULL) OR "
            "(block_scope = 2 AND cidr_prefix IS NOT NULL AND cidr_prefix BETWEEN 0 AND 128)",
            name="ck_security_ip_blocks_scope_prefix",
        ),
        CheckConstraint("hit_count >= 1", name="ck_security_ip_blocks_hit_count_pos"),
        Index(
            "idx_security_ip_blocks_ip_status_expire",
            "ip_address",
            "status",
            "expires_at",
        ),
        Index("idx_security_ip_blocks_expire", "expires_at"),
        Index("idx_security_ip_blocks_rule_time", "rule_code", "blocked_at"),
        Index("idx_security_ip_blocks_source_time", "source", "blocked_at"),
    )


__all__ = [
    "UserViolationLog",
    "UserRiskStats",
    "SecurityIPRiskStats",
    "SecurityIPBlock",
]
