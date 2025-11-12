"""
AI character related schemas.

This module contains Pydantic schemas for AI characters and contexts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from enums import AICharacterCreator
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


# Batch Operations


class BatchAICharacterDelete(BaseModel):
    """Schema for batch deleting AI characters."""

    character_qiao_ids: List[str] = Field(
        ..., min_items=1, max_items=50, description="Character external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion")
