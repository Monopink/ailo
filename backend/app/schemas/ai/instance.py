"""
AI instance related schemas.

This module contains Pydantic schemas for AI instances and contexts.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.type_aliases import JSONDict
from app.enums import AIInstanceCreator
from app.schemas.common import BaseSchema


class AIInstanceBase(BaseSchema):
    """Base AI instance schema."""

    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    creation_metadata: JSONDict = Field(
        default_factory=dict,
        description="Snapshot of creation data stored with the instance",
    )
    status: int | None = Field(1, ge=1, le=3, description="Instance status")
    relationship_id: int | None = Field(None, description="Current relationship ID")
    relationship_counts: JSONDict | None = Field(None, description="Relationship usage counts")
    memory: str | None = Field(None, description="Instance memory settings")
    prompt_variables: JSONDict | None = Field(
        None, description="Placeholder overrides used for this instance"
    )
    request_params: JSONDict | None = Field(None, description="LLM request parameter overrides")
    llm_config_id: int | None = Field(
        None, description="Preferred llm_configs.id for this instance"
    )
    timezone: str | None = Field(
        "Asia/Shanghai",
        max_length=50,
        description="IANA timezone for this instance (e.g., Asia/Shanghai)",
    )
    typing_speed_wpm: int = Field(
        ..., ge=1, description="Typing speed for this instance in words per minute"
    )


class AIInstanceCreate(BaseModel):
    """Schema for creating an AI instance."""

    user_id: int = Field(..., description="Owning user ID")
    user_qiao_id: str = Field(..., max_length=32, description="Owning user qiao_id")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    creation_metadata: JSONDict | None = Field(
        None,
        description="Snapshot of persona/template metadata captured at creation time",
    )
    memory: str | None = Field(None, description="Instance memory settings")
    placeholder_overrides: JSONDict | None = Field(
        None,
        description="Prompt placeholder overrides used to populate prompt_variables",
    )
    request_params: JSONDict | None = Field(
        None,
        description="LLM request parameters override",
        examples=[
            {
                "temperature": 0.8,
                "max_tokens": 2000,
                "top_p": 0.9,
                "frequency_penalty": 0.5,
            }
        ],
    )
    llm_config_id: int | None = Field(
        None, description="LLM config ID to associate with this instance"
    )
    relationship_id: int | None = Field(None, description="Initial relationship ID")
    relationship_counts: JSONDict | None = Field(
        None, description="Initial relationship usage counts"
    )
    status: int | None = Field(1, ge=1, le=3, description="Instance status")
    timezone: str | None = Field(
        "Asia/Shanghai",
        max_length=50,
        description="IANA timezone for this instance (e.g., Asia/Shanghai)",
    )
    typing_speed_wpm: int = Field(
        ..., ge=1, description="Typing speed for this instance in words per minute"
    )
    created_by: int | None = Field(None, description="Creator type (defaults to user if omitted)")


class AIInstanceUpdate(BaseModel):
    """Schema for updating AI instance fields."""

    style_id: int | None = Field(None, description="Style ID")
    personality_id: int | None = Field(None, description="Personality ID")
    status: int | None = Field(None, ge=1, le=3, description="Instance status")
    relationship_id: int | None = Field(None, description="Current relationship ID")
    relationship_counts: JSONDict | None = Field(None, description="Relationship usage counts")
    memory: str | None = Field(None, description="Instance memory settings")
    prompt_variables: JSONDict | None = Field(None, description="Prompt placeholder overrides")
    request_params: JSONDict | None = Field(None, description="LLM request parameter overrides")
    llm_config_id: int | None = Field(None, description="LLM config ID")
    timezone: str | None = Field(None, max_length=50, description="IANA timezone for this instance")
    typing_speed_wpm: int | None = Field(
        None, ge=1, description="Typing speed for this instance in words per minute"
    )


class AIInstanceResponse(AIInstanceBase):
    """Schema for AI instance response data."""

    id: int = Field(..., description="Internal instance ID")
    qiao_id: str = Field(..., description="Instance qiao_id")
    user_id: int = Field(..., description="Owning user ID")
    user_qiao_id: str = Field(..., description="Owning user qiao_id")
    created_by: AIInstanceCreator = Field(..., description="Creator type")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AIInstanceListResponse(BaseSchema):
    """Schema for AI instance list items."""

    id: int = Field(..., description="Internal instance ID")
    qiao_id: str = Field(..., description="Instance qiao_id")
    user_qiao_id: str = Field(..., description="Owning user qiao_id")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    creation_metadata: JSONDict = Field(
        default_factory=dict, description="Snapshot of instance creation payload"
    )
    typing_speed_wpm: int = Field(..., description="Typing speed words per minute")
    created_by: AIInstanceCreator = Field(..., description="Creator type")
    created_at: datetime = Field(..., description="Creation time")
    llm_config_id: int | None = Field(
        None, description="Preferred llm_configs.id for this instance"
    )


class BatchAIInstanceDelete(BaseModel):
    """Schema for batch deleting AI instances."""

    instance_qiao_ids: list[str] = Field(
        ..., min_length=1, max_length=50, description="Instance external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion flag")
