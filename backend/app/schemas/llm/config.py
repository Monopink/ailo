"""
LLM configuration schemas.

This module contains Pydantic schemas for LLM configurations.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, Field

from schemas.common import BaseSchema

if TYPE_CHECKING:
    from .provider import LLMProviderResponse


class LLMConfigBase(BaseSchema):
    """Base LLM configuration schema."""

    config_key: str = Field(max_length=100, description="Configuration key")
    model_name: Optional[str] = Field(default=None, max_length=100, description="Specific model name")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Temperature parameter")
    max_tokens: Optional[int] = Field(default=2000, gt=0, description="Maximum tokens")
    timeout_seconds: int = Field(default=30, gt=0, description="Timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    enable_streaming: bool = Field(default=False, description="Enable streaming output")
    enable_thinking: bool = Field(default=False, description="Enable thinking mode")
    json_schema_mode: str = Field(default="auto", description="JSON schema mode")
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")
    priority: int = Field(default=0, ge=0, description="Priority for failover")


class LLMConfigCreate(BaseModel):
    """Schema for creating an LLM configuration."""

    provider_id: int = Field(description="Provider ID")
    config_key: str = Field(max_length=100, description="Configuration key")
    model_name: Optional[str] = Field(default=None, max_length=100, description="Specific model name")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Temperature parameter")
    max_tokens: Optional[int] = Field(default=2000, gt=0, description="Maximum tokens")
    timeout_seconds: int = Field(default=30, gt=0, description="Timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    enable_streaming: bool = Field(default=False, description="Enable streaming output")
    enable_thinking: bool = Field(default=False, description="Enable thinking mode")
    json_schema_mode: str = Field(default="auto", description="JSON schema mode")
    status: int = Field(default=1, description="Status: 1=active, 2=inactive")
    priority: int = Field(default=0, ge=0, description="Priority for failover")


class LLMConfigUpdate(BaseModel):
    """Schema for updating an LLM configuration."""

    model_name: Optional[str] = Field(default=None, max_length=100, description="Specific model name")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature parameter")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="Maximum tokens")
    timeout_seconds: Optional[int] = Field(default=None, gt=0, description="Timeout in seconds")
    max_retries: Optional[int] = Field(default=None, ge=0, description="Maximum retry attempts")
    enable_streaming: Optional[bool] = Field(default=None, description="Enable streaming output")
    enable_thinking: Optional[bool] = Field(default=None, description="Enable thinking mode")
    json_schema_mode: Optional[str] = Field(default=None, description="JSON schema mode")
    status: Optional[int] = Field(default=None, description="Status: 1=active, 2=inactive")
    priority: Optional[int] = Field(default=None, ge=0, description="Priority for failover")


class LLMConfigResponse(LLMConfigBase):
    """Schema for LLM configuration response data."""

    id: int = Field(description="Configuration ID")
    provider_id: int = Field(description="Provider ID")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class LLMConfigWithProvider(LLMConfigResponse):
    """Schema for LLM configuration with provider information."""

    provider: "LLMProviderResponse" = Field(description="Provider information")
