"""AI request log related schemas.

This module contains Pydantic schemas for AI request logging and statistics.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.enums import AIRequestStatus
from app.schemas.common import BaseSchema

# AI Request Log Schemas


class AIRequestLogBase(BaseSchema):
    """Base AI request log schema."""

    instance_qiao_id: str = Field(..., max_length=32, description="Instance external ID")
    user_qiao_id: str = Field(..., max_length=32, description="User external ID")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")


class AIRequestLogCreate(BaseModel):
    """Schema for creating AI request log."""

    instance_qiao_id: str = Field(..., max_length=32, description="Instance external ID")
    user_qiao_id: str = Field(..., max_length=32, description="User external ID")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    request: dict[str, Any] = Field(..., description="Request content")
    response: dict[str, Any] | None = Field(None, description="Response content")
    status: AIRequestStatus = Field(..., description="Request status")
    token_count: int | None = Field(None, description="Token consumption")
    response_time: int | None = Field(None, description="Response time in milliseconds")
    llm_config_id: int | None = Field(None, description="LLM config ID used for this request")
    response_id: str | None = Field(None, description="Provider response ID for caching trace")
    cache_hit: bool | None = Field(False, description="Whether the request used cached tokens")
    buffer_id: int | None = Field(
        None, description="Associated buffer ID that triggered the request"
    )


class AIRequestLogUpdate(BaseModel):
    """Schema for updating AI request log."""

    response: dict[str, Any] | None = Field(None, description="Response content")
    status: AIRequestStatus | None = Field(None, description="Request status")
    token_count: int | None = Field(None, ge=0, description="Token consumption")
    response_time: int | None = Field(None, ge=0, description="Response time in milliseconds")


class AIRequestLogResponse(AIRequestLogBase):
    """Schema for AI request log response data."""

    instance_id: int = Field(..., description="Instance internal ID")
    user_id: int = Field(..., description="User internal ID")
    request: dict[str, Any] = Field(..., description="Request content")
    response: dict[str, Any] | None = Field(None, description="Response content")
    status: AIRequestStatus = Field(..., description="Request status")
    token_count: int | None = Field(None, description="Token consumption")
    response_time: int | None = Field(None, description="Response time in milliseconds")
    llm_config_id: int | None = Field(None, description="LLM config ID used for this request")
    response_id: str | None = Field(None, description="Provider response ID for caching trace")
    cache_hit: bool = Field(False, description="Whether cached tokens were used")
    buffer_id: int | None = Field(
        None, description="Associated buffer ID that triggered the request"
    )
    created_at: datetime = Field(..., description="Request time")


# AI Statistics Schemas


class AIInstanceStats(BaseSchema):
    """Schema for AI instance statistics."""

    instance_qiao_id: str = Field(..., description="Instance external ID")
    total_requests: int = Field(..., description="Total request count")
    successful_requests: int = Field(..., description="Successful request count")
    failed_requests: int = Field(..., description="Failed request count")
    total_tokens: int = Field(..., description="Total token consumption")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")
    last_request_at: datetime | None = Field(None, description="Last request time")


class AIUserStats(BaseSchema):
    """Schema for AI user statistics."""

    user_qiao_id: str = Field(..., description="User external ID")
    total_requests: int = Field(..., description="Total request count")
    successful_requests: int = Field(..., description="Successful request count")
    failed_requests: int = Field(..., description="Failed request count")
    total_tokens: int = Field(..., description="Total token consumption")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")
    active_instances: int = Field(..., description="Number of active instances")
    last_request_at: datetime | None = Field(None, description="Last request time")


class AISystemStats(BaseSchema):
    """Schema for AI system statistics."""

    total_instances: int = Field(..., description="Total instance count")
    active_instances: int = Field(..., description="Active instance count")
    total_requests: int = Field(..., description="Total request count")
    successful_requests: int = Field(..., description="Successful request count")
    failed_requests: int = Field(..., description="Failed request count")
    total_tokens: int = Field(..., description="Total token consumption")
    avg_response_time: float = Field(..., description="Average response time in milliseconds")
    requests_per_hour: float = Field(..., description="Requests per hour")
    tokens_per_hour: float = Field(..., description="Tokens per hour")
