"""
LLM provider schemas.

This module contains Pydantic schemas for LLM providers.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from schemas.common import BaseSchema


class LLMProviderBase(BaseSchema):
    """Base LLM provider schema."""

    name: str = Field(max_length=50, description="Provider identifier")
    display_name: Optional[str] = Field(default=None, max_length=100, description="Display name for UI")
    base_url: Optional[str] = Field(default=None, max_length=500, description="API base URL")
    api_key_env: Optional[str] = Field(
        default=None, max_length=100, description="Environment variable name for API key"
    )
    default_model: Optional[str] = Field(default=None, max_length=100, description="Default model name")
    supports_streaming: bool = Field(default=True, description="Supports streaming output")
    supports_json_schema: bool = Field(default=False, description="Supports JSON schema")
    supports_thinking: bool = Field(default=False, description="Supports thinking mode")


class LLMProviderCreate(BaseModel):
    """Schema for creating an LLM provider."""

    name: str = Field(max_length=50, description="Provider identifier")
    display_name: Optional[str] = Field(default=None, max_length=100, description="Display name for UI")
    base_url: Optional[str] = Field(default=None, max_length=500, description="API base URL")
    api_key_env: Optional[str] = Field(
        default=None, max_length=100, description="Environment variable name for API key"
    )
    default_model: Optional[str] = Field(default=None, max_length=100, description="Default model name")
    supports_streaming: bool = Field(default=True, description="Supports streaming output")
    supports_json_schema: bool = Field(default=False, description="Supports JSON schema")
    supports_thinking: bool = Field(default=False, description="Supports thinking mode")


class LLMProviderUpdate(BaseModel):
    """Schema for updating an LLM provider."""

    display_name: Optional[str] = Field(default=None, max_length=100, description="Display name for UI")
    base_url: Optional[str] = Field(default=None, max_length=500, description="API base URL")
    api_key_env: Optional[str] = Field(
        default=None, max_length=100, description="Environment variable name for API key"
    )
    default_model: Optional[str] = Field(default=None, max_length=100, description="Default model name")
    supports_streaming: Optional[bool] = Field(default=None, description="Supports streaming output")
    supports_json_schema: Optional[bool] = Field(default=None, description="Supports JSON schema")
    supports_thinking: Optional[bool] = Field(default=None, description="Supports thinking mode")
    status: Optional[int] = Field(default=None, description="Status")


class LLMProviderResponse(LLMProviderBase):
    """Schema for LLM provider response data."""

    id: int = Field(description="Provider ID")
    status: int = Field(description="Status")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")
