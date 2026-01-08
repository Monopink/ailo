"""LLM configuration schemas.

This module contains Pydantic schemas for LLM configurations.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema

if TYPE_CHECKING:
    from .provider import LLMProviderResponse


class ThinkingMode(str, Enum):
    """Thinking mode enumeration."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    AUTO = "auto"


class ToolChoice(str, Enum):
    """Tool choice preferences."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"


class LLMConfigBase(BaseSchema):
    """Base LLM configuration schema."""

    name: str = Field(max_length=100, description="Configuration name")
    model_name: str | None = Field(default=None, max_length=100, description="Specific model name")
    temperature: float | None = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature parameter"
    )
    max_tokens: int | None = Field(default=4000, gt=0, description="Maximum tokens")
    timeout_seconds: int = Field(default=60, gt=0, description="Timeout in seconds")
    thinking_mode: ThinkingMode = Field(
        default=ThinkingMode.AUTO, description="Thinking mode: enabled/disabled/auto"
    )
    top_p: float = Field(default=0.70, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    frequency_penalty: float = Field(default=0.00, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.00, ge=-2.0, le=2.0, description="Presence penalty")
    stop_sequences: list[str] = Field(default_factory=list, description="Stop sequences (max 4)")
    json_schema_mode: str = Field(default="auto", description="JSON schema mode")
    default_tools: list[dict[str, Any]] = Field(
        default_factory=list, description="Default tool definitions"
    )
    default_tool_choice: ToolChoice = Field(
        default=ToolChoice.AUTO, description="How the model decides whether to call tools"
    )
    parallel_tool_calls: bool = Field(
        default=False, description="Allow provider to execute tools in parallel"
    )
    max_tool_calls: int = Field(
        default=1, ge=0, description="Maximum number of tool calls per request"
    )
    default_extra_headers: dict[str, Any] = Field(
        default_factory=dict, description="Default extra headers attached to provider requests"
    )
    default_extra_query: dict[str, Any] = Field(
        default_factory=dict,
        description="Default extra query parameters attached to provider requests",
    )
    enable_streaming: bool = Field(
        default=False, description="Enable streaming output (experimental)"
    )
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")
    priority: int = Field(default=1, ge=0, description="Priority for failover")
    extra_params: dict[str, Any] | None = Field(
        default=None, description="Provider-specific parameters (JSON object)"
    )


class LLMConfigCreate(BaseModel):
    """Schema for creating an LLM configuration."""

    provider_id: int = Field(description="Provider ID")
    name: str = Field(max_length=100, description="Configuration name")
    model_name: str | None = Field(default=None, max_length=100, description="Specific model name")
    temperature: float | None = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature parameter"
    )
    max_tokens: int | None = Field(default=4000, gt=0, description="Maximum tokens")
    timeout_seconds: int = Field(default=60, gt=0, description="Timeout in seconds")
    thinking_mode: ThinkingMode = Field(
        default=ThinkingMode.AUTO, description="Thinking mode: enabled/disabled/auto"
    )
    top_p: float = Field(default=0.70, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    frequency_penalty: float = Field(default=0.00, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.00, ge=-2.0, le=2.0, description="Presence penalty")
    stop_sequences: list[str] = Field(default_factory=list, description="Stop sequences (max 4)")
    json_schema_mode: str = Field(default="auto", description="JSON schema mode")
    default_tools: list[dict[str, Any]] = Field(
        default_factory=list, description="Default tool definitions"
    )
    default_tool_choice: ToolChoice = Field(
        default=ToolChoice.AUTO, description="How the model decides whether to call tools"
    )
    parallel_tool_calls: bool = Field(
        default=False, description="Allow provider to execute tools in parallel"
    )
    max_tool_calls: int = Field(
        default=1, ge=0, description="Maximum number of tool calls per request"
    )
    default_extra_headers: dict[str, Any] = Field(
        default_factory=dict, description="Default extra headers attached to provider requests"
    )
    default_extra_query: dict[str, Any] = Field(
        default_factory=dict,
        description="Default extra query parameters attached to provider requests",
    )
    enable_streaming: bool = Field(
        default=False, description="Enable streaming output (experimental)"
    )
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")
    priority: int = Field(default=1, ge=0, description="Priority for failover")
    extra_params: dict[str, Any] | None = Field(
        default=None, description="Provider-specific parameters (JSON object)"
    )


class LLMConfigUpdate(BaseModel):
    """Schema for updating an LLM configuration."""

    model_name: str | None = Field(default=None, max_length=100, description="Specific model name")
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Temperature parameter"
    )
    max_tokens: int | None = Field(default=None, gt=0, description="Maximum tokens")
    timeout_seconds: int | None = Field(default=None, gt=0, description="Timeout in seconds")
    thinking_mode: ThinkingMode | None = Field(
        default=None, description="Thinking mode: enabled/disabled/auto"
    )
    top_p: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling threshold"
    )
    frequency_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: float | None = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    stop_sequences: list[str] | None = Field(default=None, description="Stop sequences (max 4)")
    json_schema_mode: str | None = Field(default=None, description="JSON schema mode")
    default_tools: list[dict[str, Any]] | None = Field(
        default=None, description="Default tool definitions"
    )
    default_tool_choice: ToolChoice | None = Field(default=None, description="Tool choice behavior")
    parallel_tool_calls: bool | None = Field(
        default=None, description="Allow provider to execute tools in parallel"
    )
    max_tool_calls: int | None = Field(
        default=None, ge=0, description="Maximum number of tool calls per request"
    )
    default_extra_headers: dict[str, Any] | None = Field(
        default=None, description="Default extra headers attached to provider requests"
    )
    default_extra_query: dict[str, Any] | None = Field(
        default=None, description="Default extra query parameters attached to provider requests"
    )
    enable_streaming: bool | None = Field(
        default=None, description="Enable streaming output (experimental)"
    )
    status: int | None = Field(default=None, description="Status: 1=active, 2=inactive")
    priority: int | None = Field(default=None, ge=0, description="Priority for failover")
    extra_params: dict[str, Any] | None = Field(
        default=None, description="Provider-specific parameters (JSON object)"
    )


class LLMConfigResponse(LLMConfigBase):
    """Schema for LLM configuration response data."""

    id: int = Field(description="Configuration ID")
    provider_id: int = Field(description="Provider ID")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class LLMConfigWithProvider(LLMConfigResponse):
    """Schema for LLM configuration with provider information."""

    provider: "LLMProviderResponse" = Field(default=..., description="Provider information")
