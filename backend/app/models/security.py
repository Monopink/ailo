"""
Security monitoring related models.

This module contains SQLAlchemy models for user security logs and statistics.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import AutoAction, ManualReviewStatus, RiskLevel
from app.models.base import SnowflakeModel
from app.type_defs import JSONDict


class UserViolationLog(SnowflakeModel):
    """
    User violation log model.

    User security violation records.
    """

    __tablename__ = "user_violation_logs"

    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="User ID, references users.id"
    )

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
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
            "Violation type: 1=prompt_injection, 2=abuse_content, 3=spam, 4=harassment, 5=other"
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


class UserRiskStats(SnowflakeModel):
    """
    User risk stats model.

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
            'Violations by type: {"prompt_injection": 5, "abuse": 2} (JSONB for better performance)'
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
