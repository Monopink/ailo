"""
LLM test log schemas.

This module contains Pydantic schemas for LLM test logs.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class LLMTestLogCreate(BaseModel):
    """Schema for creating an LLM test log."""

    id: int = Field(description="Snowflake ID")
    config_id: int = Field(description="Configuration ID")
    config_name: str = Field(max_length=100, description="Configuration name")
    provider_name: str = Field(max_length=50, description="Provider name")
    model_name: Optional[str] = Field(default=None, max_length=100, description="Model name")
    test_message: str = Field(description="Test message content")
    override_temperature: Optional[float] = Field(default=None, description="Override temperature")
    override_max_tokens: Optional[int] = Field(default=None, description="Override max tokens")
    thinking_mode: str = Field(description="Thinking mode: enabled/disabled/auto")
    request: Dict[str, Any] = Field(description="Complete request payload")
    response: Optional[Dict[str, Any]] = Field(default=None, description="Complete response data")
    status: int = Field(description="Status: 1=success, 2=failed, 3=timeout")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    response_time_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")
    prompt_tokens: Optional[int] = Field(default=None, description="Prompt tokens count")
    completion_tokens: Optional[int] = Field(default=None, description="Completion tokens count")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens count")
    reasoning_content: Optional[str] = Field(default=None, description="Thinking process content")
    completed_at: Optional[datetime] = Field(default=None, description="Test completion timestamp")


class LLMTestLogUpdate(BaseModel):
    """Schema for updating an LLM test log (not used - logs are immutable)."""

    pass
