"""LLM test log model.

This module contains SQLAlchemy model for LLM configuration testing logs.
"""

from datetime import datetime

from sqlalchemy import DECIMAL, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import ImmutableSnowflakeModel
from app.type_defs import JSONDict


class LLMTestLog(ImmutableSnowflakeModel):
    """LLM test log model.

    Records LLM configuration tests performed through admin interface.
    Test logs are immutable - no updated_at field needed.
    """

    __tablename__ = "llm_test_logs"

    config_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Configuration ID, references llm_configs.id"
    )

    config_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Configuration name (redundant for query convenience)"
    )

    provider_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Provider name (redundant for query convenience)"
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Model name used for the test"
    )

    # Test parameters
    test_message: Mapped[str] = mapped_column(Text, nullable=False, comment="Test message content")

    override_temperature: Mapped[float | None] = mapped_column(
        DECIMAL(3, 2), nullable=True, comment="Override temperature parameter (0.0-2.0)"
    )

    override_max_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Override max tokens parameter"
    )

    thinking_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Thinking mode: enabled/disabled/auto"
    )

    enable_json_schema: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Enable JSON Schema mode: 0=no, 1=yes"
    )

    # Request and response
    request: Mapped[JSONDict] = mapped_column(
        JSONB, nullable=False, comment="Complete request payload"
    )

    response: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Complete response data"
    )

    # Execution results
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Status: 1=success, 2=failed, 3=timeout"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if test failed"
    )

    # Performance metrics
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    prompt_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Prompt tokens count"
    )

    completion_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Completion tokens count"
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total tokens count"
    )

    # Thinking mode related
    reasoning_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Thinking process content (when thinking mode enabled)"
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Test completion timestamp"
    )
