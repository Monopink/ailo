"""
LLM test log schemas.

This module contains Pydantic schemas for LLM test logs.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LLMTestLogCreate(BaseModel):
    """Schema for creating an LLM test log."""

    id: int = Field(description="Snowflake ID")
    config_id: int = Field(description="Configuration ID")
    config_name: str = Field(max_length=100, description="Configuration name")
    provider_name: str = Field(max_length=50, description="Provider name")
    model_name: str | None = Field(default=None, max_length=100, description="Model name")
    test_message: str = Field(description="Test message content")
    override_temperature: float | None = Field(default=None, description="Override temperature")
    override_max_tokens: int | None = Field(default=None, description="Override max tokens")
    thinking_mode: str = Field(description="Thinking mode: enabled/disabled/auto")
    request: dict[str, Any] = Field(description="Complete request payload")
    response: dict[str, Any] | None = Field(default=None, description="Complete response data")
    status: int = Field(description="Status: 1=success, 2=failed, 3=timeout")
    error_message: str | None = Field(default=None, description="Error message if failed")
    response_time_ms: int | None = Field(default=None, description="Response time in milliseconds")
    prompt_tokens: int | None = Field(default=None, description="Prompt tokens count")
    completion_tokens: int | None = Field(default=None, description="Completion tokens count")
    total_tokens: int | None = Field(default=None, description="Total tokens count")
    reasoning_content: str | None = Field(default=None, description="Thinking process content")
    completed_at: datetime | None = Field(default=None, description="Test completion timestamp")


class LLMTestLogUpdate(BaseModel):
    """Schema for updating an LLM test log (not used - logs are immutable)."""
