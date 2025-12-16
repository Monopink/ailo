"""
System configuration related schemas.

This module contains Pydantic schemas for system configuration management.
"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from app.enums import ConfigType
from app.schemas.common import BaseSchema

# System Configuration Schemas


class SystemConfigBase(BaseSchema):
    """Base system configuration schema."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: str | None = Field(None, max_length=500, description="Configuration description")


class SystemConfigCreate(BaseModel):
    """Schema for creating system configuration."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: str | None = Field(None, max_length=500, description="Configuration description")

    @field_validator("config_value", mode="after")
    @classmethod
    def validate_config_value_by_type(cls, value: str, info: ValidationInfo) -> str:
        """Validate config_value based on config_type."""
        config_type = info.data.get("config_type")
        if config_type == ConfigType.NUMBER:
            try:
                float(value)
            except ValueError:
                raise ValueError("config_value must be a valid number for NUMBER type")
        elif config_type == ConfigType.BOOLEAN:
            if value.lower() not in ["true", "false", "1", "0"]:
                raise ValueError("config_value must be true/false or 1/0 for BOOLEAN type")
        elif config_type == ConfigType.JSON:
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("config_value must be valid JSON for JSON type")
        return value


class SystemConfigUpdate(BaseModel):
    """Schema for updating system configuration."""

    config_value: str | None = Field(None, description="Configuration value")
    config_type: ConfigType | None = Field(None, description="Value type")
    description: str | None = Field(None, max_length=500, description="Configuration description")

    @field_validator("config_value", mode="after")
    @classmethod
    def validate_config_value_by_type(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Validate config_value based on config_type."""
        if value is None:
            return value
        config_type = info.data.get("config_type")
        if config_type == ConfigType.NUMBER:
            try:
                float(value)
            except ValueError:
                raise ValueError("config_value must be a valid number for NUMBER type")
        elif config_type == ConfigType.BOOLEAN:
            if value.lower() not in ["true", "false", "1", "0"]:
                raise ValueError("config_value must be true/false or 1/0 for BOOLEAN type")
        elif config_type == ConfigType.JSON:
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("config_value must be valid JSON for JSON type")
        return value


class SystemConfigResponse(SystemConfigBase):
    """Schema for system configuration response data."""

    updated_by: int | None = Field(None, description="Updated by admin user ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class SystemConfigListResponse(BaseSchema):
    """Schema for system configuration list item."""

    config_key: str = Field(..., description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: str | None = Field(None, description="Configuration description")
    is_public: bool = Field(..., description="Is public configuration")
    updated_at: datetime = Field(..., description="Last update time")


# Configuration Value Schemas


class ConfigValueResponse(BaseSchema):
    """Schema for configuration value response."""

    config_key: str = Field(..., description="Configuration key")
    value: str | int | float | bool | dict[str, Any] = Field(
        ..., description="Parsed configuration value"
    )
    config_type: ConfigType = Field(..., description="Value type")


# Batch Configuration Operations


class BatchConfigUpdate(BaseModel):
    """Schema for batch updating configurations."""

    configs: dict[str, Any] = Field(..., description="Configuration key-value pairs")

    @field_validator("configs")
    @classmethod
    def validate_configs(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration dictionary."""
        if not value:
            raise ValueError("configs cannot be empty")
        if len(value) > 50:
            raise ValueError("Cannot update more than 50 configurations at once")
        return value


class BatchConfigDelete(BaseModel):
    """Schema for batch deleting configurations."""

    config_keys: list[str] = Field(
        ..., min_length=1, max_length=50, description="Configuration keys to delete"
    )
