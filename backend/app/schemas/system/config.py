"""
System configuration related schemas.

This module contains Pydantic schemas for system configuration management.
"""

from datetime import datetime
from typing import Any, Optional, Union
from pydantic import BaseModel, Field, validator

from enums import ConfigType
from schemas.common import BaseSchema


# System Configuration Schemas


class SystemConfigBase(BaseSchema):
    """Base system configuration schema."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    is_public: bool = Field(False, description="Is public configuration")


class SystemConfigCreate(BaseModel):
    """Schema for creating system configuration."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    is_public: bool = Field(False, description="Is public configuration")

    @validator("config_value")
    def validate_config_value_by_type(cls, v, values):
        """Validate config_value based on config_type."""
        config_type = values.get("config_type")
        if config_type == ConfigType.NUMBER:
            try:
                float(v)
            except ValueError:
                raise ValueError("config_value must be a valid number for NUMBER type")
        elif config_type == ConfigType.BOOLEAN:
            if v.lower() not in ["true", "false", "1", "0"]:
                raise ValueError("config_value must be true/false or 1/0 for BOOLEAN type")
        elif config_type == ConfigType.JSON:
            import json

            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("config_value must be valid JSON for JSON type")
        return v


class SystemConfigUpdate(BaseModel):
    """Schema for updating system configuration."""

    config_value: Optional[str] = Field(None, description="Configuration value")
    config_type: Optional[ConfigType] = Field(None, description="Value type")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    is_public: Optional[bool] = Field(None, description="Is public configuration")

    @validator("config_value")
    def validate_config_value_by_type(cls, v, values):
        """Validate config_value based on config_type."""
        if v is None:
            return v
        config_type = values.get("config_type")
        if config_type == ConfigType.NUMBER:
            try:
                float(v)
            except ValueError:
                raise ValueError("config_value must be a valid number for NUMBER type")
        elif config_type == ConfigType.BOOLEAN:
            if v.lower() not in ["true", "false", "1", "0"]:
                raise ValueError("config_value must be true/false or 1/0 for BOOLEAN type")
        elif config_type == ConfigType.JSON:
            import json

            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("config_value must be valid JSON for JSON type")
        return v


class SystemConfigResponse(SystemConfigBase):
    """Schema for system configuration response data."""

    updated_by: Optional[int] = Field(None, description="Updated by admin user ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class SystemConfigListResponse(BaseSchema):
    """Schema for system configuration list item."""

    config_key: str = Field(..., description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    config_type: ConfigType = Field(..., description="Value type")
    description: Optional[str] = Field(None, description="Configuration description")
    is_public: bool = Field(..., description="Is public configuration")
    updated_at: datetime = Field(..., description="Last update time")


# Configuration Value Schemas


class ConfigValueResponse(BaseSchema):
    """Schema for configuration value response."""

    config_key: str = Field(..., description="Configuration key")
    value: Union[str, int, float, bool, dict] = Field(..., description="Parsed configuration value")
    config_type: ConfigType = Field(..., description="Value type")


# Batch Configuration Operations


class BatchConfigUpdate(BaseModel):
    """Schema for batch updating configurations."""

    configs: dict = Field(..., description="Configuration key-value pairs")

    @validator("configs")
    def validate_configs(cls, v):
        """Validate configuration dictionary."""
        if not v:
            raise ValueError("configs cannot be empty")
        if len(v) > 50:
            raise ValueError("Cannot update more than 50 configurations at once")
        return v


class BatchConfigDelete(BaseModel):
    """Schema for batch deleting configurations."""

    config_keys: list = Field(..., min_items=1, max_items=50, description="Configuration keys to delete")
