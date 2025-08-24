"""
AI character related schemas.

This module contains Pydantic schemas for AI characters and contexts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from enums import AICharacterCreator, AIContextRole, AIContextSourceType
from schemas.common import BaseSchema


# AI Character Schemas


class AICharacterBase(BaseSchema):
    """Base AI character schema."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")


class AICharacterCreate(BaseModel):
    """Schema for creating an AI character."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    style_id: int = Field(..., description="Style ID")
    personality_id: int = Field(..., description="Personality ID")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")
    score_offset_algorithm: Optional[str] = Field(
        None, max_length=100, description="Score offset algorithm"
    )
    score_offset_coefficient: Optional[float] = Field(None, description="Score offset coefficient")


class AICharacterUpdate(BaseModel):
    """Schema for updating AI character."""

    category: Optional[str] = Field(None, max_length=50, description="Character category")
    memory: Optional[str] = Field(None, description="Character memory settings")
    placeholder_overrides: Optional[Dict[str, Any]] = Field(None, description="Placeholder overrides")
    score_offset_algorithm: Optional[str] = Field(
        None, max_length=100, description="Score offset algorithm"
    )
    score_offset_coefficient: Optional[float] = Field(None, description="Score offset coefficient")


class AICharacterResponse(AICharacterBase):
    """Schema for AI character response data."""

    qiao_id: str = Field(..., description="Character external ID")
    user_id: Optional[int] = Field(None, description="Owner user ID")
    user_qiao_id: Optional[str] = Field(None, description="Owner user external ID")
    score_offset_algorithm: Optional[str] = Field(None, description="Score offset algorithm")
    score_offset_coefficient: Optional[float] = Field(None, description="Score offset coefficient")
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
    source_type: AIContextSourceType = Field(AIContextSourceType.ORIGINAL, description="Source type")
    source_message_ids: Optional[List[str]] = Field(None, description="Source message ID list")
    context_metadata: Optional[Dict[str, Any]] = Field(None, description="Context metadata")
    position: int = Field(..., description="Position in conversation sequence")
    token_count: Optional[int] = Field(None, description="Token count")


class AIContextResponse(AIContextBase):
    """Schema for AI context response data."""

    character_id: int = Field(..., description="Character internal ID")
    user_id: int = Field(..., description="User internal ID")
    source_type: AIContextSourceType = Field(..., description="Source type")
    source_message_ids: Optional[List[str]] = Field(None, description="Source message ID list")
    context_metadata: Optional[Dict[str, Any]] = Field(None, description="Context metadata")
    position: int = Field(..., description="Position in conversation sequence")
    token_count: Optional[int] = Field(None, description="Token count")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# Batch Operations


class BatchAICharacterDelete(BaseModel):
    """Schema for batch deleting AI characters."""

    character_qiao_ids: List[str] = Field(
        ..., min_items=1, max_items=50, description="Character external IDs"
    )
    permanent: bool = Field(False, description="Permanent deletion")
