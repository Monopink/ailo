"""
LLM test log model.

This module contains SQLAlchemy model for LLM configuration testing logs.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Integer, String, Text, DECIMAL, Index, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import ImmutableSnowflakeModel


class LLMTestLog(ImmutableSnowflakeModel):
    """
    LLM test log model.

    Records LLM configuration tests performed through admin interface.
    Test logs are immutable - no updated_at field needed.
    """

    __tablename__ = "llm_test_logs"

    config_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Configuration ID, references llm_configs.id"
    )

    config_key: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Configuration key (redundant for query convenience)"
    )

    provider_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Provider name (redundant for query convenience)"
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Model name used for the test"
    )

    # Test parameters
    test_message: Mapped[str] = mapped_column(Text, nullable=False, comment="Test message content")

    override_temperature: Mapped[Optional[float]] = mapped_column(
        DECIMAL(3, 2), nullable=True, comment="Override temperature parameter (0.0-2.0)"
    )

    override_max_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Override max tokens parameter"
    )

    enable_thinking: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Enable thinking mode: 0=no, 1=yes"
    )

    # Request and response
    request: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="Complete request payload"
    )

    response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Complete response data"
    )

    # Execution results
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Status: 1=success, 2=failed, 3=timeout"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error message if test failed"
    )

    # Performance metrics
    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Prompt tokens count"
    )

    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Completion tokens count"
    )

    total_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Total tokens count"
    )

    # Thinking mode related
    reasoning_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Thinking process content (when thinking mode enabled)"
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Test completion timestamp"
    )

    # Indexes
    __table_args__ = (
        Index("idx_llm_test_logs_config_id", "config_id"),
        Index("idx_llm_test_logs_status", "status"),
        Index("idx_llm_test_logs_created_at", "created_at"),
    )
