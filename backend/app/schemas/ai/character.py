"""
AI character related schemas.

This module contains Pydantic schemas for AI characters and contexts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from enums import AICharacterCreator, AIContextRole, AIAggregateState
from schemas.common import BaseSchema


# AI Character Schemas


class AICharacterBase(BaseSchema):
    """Base AI character schema."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")
    request_params: Optional[Dict[str, Any]] = Field(
        None, description="LLM request parameters override (temperature, max_tokens, etc.)"
    )
    created_from_profile_qiao_id: Optional[str] = Field(
        None, max_length=32, description="Source profile template qiao_id (if created from template)"
    )


class AICharacterCreate(BaseModel):
    """Schema for creating an AI character."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")
    request_params: Optional[Dict[str, Any]] = Field(
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
    created_from_profile_qiao_id: Optional[str] = Field(
        None, max_length=32, description="Source profile template qiao_id (if created from template)"
    )


class AICharacterUpdate(BaseModel):
    """Schema for updating AI character."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")
    request_params: Optional[Dict[str, Any]] = Field(None, description="LLM request parameters override")
    created_from_profile_qiao_id: Optional[str] = Field(
        None, max_length=32, description="Source profile template qiao_id (if created from template)"
    )


class AICharacterResponse(AICharacterBase):
    """Schema for AI character response data."""

    qiao_id: str = Field(..., description="Character external ID")
    user_id: Optional[int] = Field(None, description="Owner user ID")
    user_qiao_id: Optional[str] = Field(None, description="Owner user external ID")
    created_by: AICharacterCreator = Field(..., description="Creator type")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AICharacterListResponse(BaseSchema):
    """Schema for AI character list item."""

    qiao_id: str = Field(..., description="Character external ID")
    category: Optional[str] = Field(None, description="Character category")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    created_by: AICharacterCreator = Field(..., description="Creator type")
    created_at: datetime = Field(..., description="Creation time")


# AI Context Schemas


class AIContextBase(BaseSchema):
    """Base AI context schema."""

    character_qiao_id: str = Field(..., max_length=32, description="Character external ID")
    user_qiao_id: str = Field(..., max_length=32, description="User external ID")
    role: AIContextRole = Field(..., description="Role type")
    content: str = Field(..., description="Message content")


class AIContextCreate(BaseModel):
    """Schema for creating AI context."""

    character_qiao_id: str = Field(..., max_length=32, description="Character external ID")
    user_qiao_id: str = Field(..., max_length=32, description="User external ID")
    role: AIContextRole = Field(..., description="Role type")
    content: str = Field(..., min_length=1, description="Message content")
    first_msg_id_client: Optional[str] = Field(None, max_length=64, description="First message client ID")
    last_msg_id_client: Optional[str] = Field(None, max_length=64, description="Last message client ID")
    token_count: Optional[int] = Field(None, description="Token count")
    last_msg_time_ms: Optional[int] = Field(None, description="Last message time (milliseconds)")
    buffer_expires_at_ms: Optional[int] = Field(None, description="Buffer expiration time (milliseconds)")
    aggregate_state: Optional[int] = Field(None, description="Aggregate state (user only)")


class AIContextUpdate(BaseModel):
    """Schema for updating AI context."""

    role: Optional[AIContextRole] = Field(default=None, description="Role type")
    content: Optional[str] = Field(default=None, description="Message content")
    first_msg_id_client: Optional[str] = Field(default=None, description="First message client ID")
    last_msg_id_client: Optional[str] = Field(default=None, description="Last message client ID")
    token_count: Optional[int] = Field(default=None, description="Token count")
    last_msg_time_ms: Optional[int] = Field(default=None, description="Last message time (milliseconds)")
    buffer_expires_at_ms: Optional[int] = Field(
        default=None, description="Buffer expiration time (milliseconds)"
    )
    aggregate_state: Optional[int] = Field(default=None, description="Aggregate state")


class AIContextResponse(AIContextBase):
    """Schema for AI context response data."""

    character_id: int = Field(..., description="Character internal ID")
    user_id: int = Field(..., description="User internal ID")
    first_msg_id_client: Optional[str] = Field(None, description="First message client ID")
    last_msg_id_client: Optional[str] = Field(None, description="Last message client ID")
    token_count: Optional[int] = Field(None, description="Token count")
    last_msg_time_ms: Optional[int] = Field(None, description="Last message time (milliseconds)")
    buffer_expires_at_ms: Optional[int] = Field(None, description="Buffer expiration time (milliseconds)")
    aggregate_state: Optional[int] = Field(None, description="Aggregate state")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# Batch Operations


class BatchAICharacterDelete(BaseModel):
    """Schema for batch deleting AI characters."""

    character_qiao_ids: List[str] = Field(
        ..., min_items=1, max_items=50, description="Character external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion")
