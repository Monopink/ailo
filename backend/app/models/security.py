"""
Security monitoring related models.

This module contains SQLAlchemy models for user security logs and statistics.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from enums import AutoAction, ManualReviewStatus, RiskLevel
from models.base import SnowflakeModel


class UserSecurityLog(SnowflakeModel):
    """
    User security log model.

    User security violation records.
    """

    __tablename__ = "user_security_logs"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User ID, references users.id")

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="User external ID")

    character_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Character ID if related to specific AI"
    )

    character_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Character external ID"
    )

    violation_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Violation type: 1=prompt_injection, 2=abuse_content, 3=spam, 4=harassment, 5=other",
    )

    severity_level: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Severity: 1=low, 2=medium, 3=high, 4=critical"
    )

    original_message: Mapped[str] = mapped_column(Text, nullable=False, comment="Original user message")

    ai_detection_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="AI detection result (JSONB for better performance)"
    )

    confidence_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Confidence score (0-100)"
    )

    auto_action_taken: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=AutoAction.NONE,
        comment="Auto action: 1=none, 2=warning, 3=restrict, 4=suspend",
    )

    manual_review_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ManualReviewStatus.PENDING,
        comment="Manual review: 1=pending, 2=confirmed, 3=false_positive, 4=ignored",
    )

    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Reviewer admin ID")

    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Review notes")

    # Indexes
    __table_args__ = (
        Index("idx_user_security_logs_user_id", "user_id"),
        Index("idx_user_security_logs_user_qiao_id", "user_qiao_id"),
        Index("idx_user_security_logs_character_id", "character_id"),
        Index("idx_user_security_logs_violation_type", "violation_type"),
        Index("idx_user_security_logs_severity_level", "severity_level"),
        Index("idx_user_security_logs_auto_action_taken", "auto_action_taken"),
        Index("idx_user_security_logs_manual_review_status", "manual_review_status"),
        Index("idx_user_security_logs_created_at", "created_at"),
    )


class UserSecurityStats(SnowflakeModel):
    """
    User security stats model.

    User security statistics summary.
    """

    __tablename__ = "user_security_stats"

    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, comment="User ID, references users.id"
    )

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="User external ID"
    )

    total_violations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total violation count"
    )

    violation_by_type: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment='Violations by type: {"prompt_injection": 5, "abuse": 2} (JSONB for better performance)',
    )

    last_violation_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Last violation time"
    )

    current_risk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=RiskLevel.LOW,
        comment="Risk level: 1=low, 2=medium, 3=high, 4=banned",
    )

    consecutive_violations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Consecutive violations (reset after 7 days)"
    )

    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Warning count")

    restriction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Restriction count"
    )

    suspension_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Suspension count"
    )

    last_action_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="Last action time"
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_security_stats_user_id", "user_id"),
        Index("idx_user_security_stats_user_qiao_id", "user_qiao_id"),
        Index("idx_user_security_stats_current_risk_level", "current_risk_level"),
        Index("idx_user_security_stats_total_violations", "total_violations"),
        Index("idx_user_security_stats_last_violation_at", "last_violation_at"),
    )
