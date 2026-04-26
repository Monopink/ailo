"""System configuration related schemas.

This module contains Pydantic schemas for system configuration management.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from app.enums import ConfigShape, ConfigValueType, SystemConfigScope
from app.schemas.common import BaseSchema
from app.type_defs import JSONValue

MAX_CONFIG_BATCH_UPDATE = 50


def _normalize_single_value(  # noqa: PLR0911
    *,
    value_type: ConfigValueType,
    value: JSONValue,
    field_name: str,
) -> JSONValue:
    if value_type == ConfigValueType.NUMBER:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a valid integer for NUMBER type")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be a valid integer for NUMBER type") from exc
        raise ValueError(f"{field_name} must be a valid integer for NUMBER type")

    if value_type == ConfigValueType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        raise ValueError(f"{field_name} must be true/false for BOOLEAN type")

    if value_type in {ConfigValueType.STRING, ConfigValueType.ENUM}:
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(f"{field_name} must be a non-empty string for STRING/ENUM type")
        return value.strip()

    return value


def _normalize_value_by_shape(
    *,
    value_type: ConfigValueType,
    config_shape: ConfigShape,
    value: JSONValue,
    field_name: str,
) -> JSONValue:
    if config_shape == ConfigShape.SINGLE:
        return _normalize_single_value(value_type=value_type, value=value, field_name=field_name)

    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a non-empty array when config_shape is ARRAY")

    normalized_items: list[JSONValue] = []
    for item in value:
        normalized_items.append(
            _normalize_single_value(
                value_type=value_type,
                value=item,
                field_name=field_name,
            )
        )
    if len(normalized_items) == 0:
        raise ValueError(f"{field_name} must be a non-empty array when config_shape is ARRAY")
    return normalized_items


class SystemConfigBase(BaseSchema):
    """Base system configuration schema."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: JSONValue = Field(..., description="Configuration value")
    value_type: ConfigValueType = Field(..., description="Value type")
    config_shape: ConfigShape = Field(..., description="Configuration shape")
    config_scope: SystemConfigScope = Field(..., description="Configuration scope")
    description: str | None = Field(None, max_length=500, description="Configuration description")


class SystemConfigCreate(BaseModel):
    """Schema for creating system configuration."""

    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: JSONValue = Field(..., description="Configuration value")
    value_type: ConfigValueType = Field(..., description="Value type")
    config_shape: ConfigShape = Field(..., description="Configuration shape")
    config_scope: SystemConfigScope = Field(..., description="Configuration scope")
    description: str | None = Field(None, max_length=500, description="Configuration description")

    @field_validator("config_value", mode="after")
    @classmethod
    def validate_config_value_by_type_and_shape(
        cls, value: JSONValue, info: ValidationInfo
    ) -> JSONValue:
        """Validate config_value based on value_type and config_shape."""
        value_type = info.data.get("value_type")
        config_shape = info.data.get("config_shape")
        if value_type is None or config_shape is None:
            return value
        return _normalize_value_by_shape(
            value_type=value_type,
            config_shape=config_shape,
            value=value,
            field_name="config_value",
        )


class SystemConfigUpdate(BaseModel):
    """Schema for updating system configuration."""

    config_value: JSONValue | None = Field(None, description="Configuration value")
    value_type: ConfigValueType | None = Field(None, description="Value type")
    config_shape: ConfigShape | None = Field(None, description="Configuration shape")
    config_scope: SystemConfigScope | None = Field(None, description="Configuration scope")
    description: str | None = Field(None, max_length=500, description="Configuration description")

    @field_validator("config_value", mode="after")
    @classmethod
    def validate_config_value_by_type_and_shape(
        cls, value: JSONValue | None, info: ValidationInfo
    ) -> JSONValue | None:
        """Validate config_value based on value_type/config_shape when both are provided."""
        if value is None:
            return value

        value_type = info.data.get("value_type")
        config_shape = info.data.get("config_shape")
        if value_type is None or config_shape is None:
            return value

        return _normalize_value_by_shape(
            value_type=value_type,
            config_shape=config_shape,
            value=value,
            field_name="config_value",
        )


class SystemConfigResponse(SystemConfigBase):
    """Schema for system configuration response data."""

    updated_by: int | None = Field(None, description="Updated by admin user ID")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class SystemConfigListResponse(BaseSchema):
    """Schema for system configuration list item."""

    config_key: str = Field(..., description="Configuration key")
    config_value: JSONValue = Field(..., description="Configuration value")
    value_type: ConfigValueType = Field(..., description="Value type")
    config_shape: ConfigShape = Field(..., description="Configuration shape")
    config_scope: SystemConfigScope = Field(..., description="Configuration scope")
    description: str | None = Field(None, description="Configuration description")
    is_public: bool = Field(..., description="Is public configuration")
    updated_at: datetime = Field(..., description="Last update time")


class ConfigValueResponse(BaseSchema):
    """Schema for configuration value response."""

    config_key: str = Field(..., description="Configuration key")
    value: JSONValue = Field(..., description="Parsed configuration value")
    value_type: ConfigValueType = Field(..., description="Value type")


class BatchConfigUpdate(BaseModel):
    """Schema for batch updating configurations."""

    configs: dict[str, Any] = Field(..., description="Configuration key-value pairs")

    @field_validator("configs")
    @classmethod
    def validate_configs(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration dictionary."""
        if not value:
            raise ValueError("configs cannot be empty")
        if len(value) > MAX_CONFIG_BATCH_UPDATE:
            raise ValueError("Cannot update more than 50 configurations at once")
        return value


class BatchConfigDelete(BaseModel):
    """Schema for batch deleting configurations."""

    config_keys: list[str] = Field(
        ..., min_length=1, max_length=50, description="Configuration keys to delete"
    )
