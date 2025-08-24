"""
AI chat related schemas.

This module contains Pydantic schemas for AI chat interactions and relationship scoring.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from schemas.common import BaseSchema


# AI Chat Request/Response Schemas


class AIChatRequest(BaseModel):
    """Schema for AI chat request."""

    character_qiao_id: str = Field(..., max_length=32, description="Character external ID")
    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    context_limit: int = Field(10, ge=1, le=50, description="Maximum context messages to include")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="AI temperature setting")
    max_tokens: Optional[int] = Field(None, ge=1, le=4000, description="Maximum response tokens")


class AIChatResponse(BaseSchema):
    """Schema for AI chat response."""

    message: str = Field(..., description="AI response message")
    character_qiao_id: str = Field(..., description="Character external ID")
    token_count: Optional[int] = Field(None, description="Token consumption")
    response_time: int = Field(..., description="Response time in milliseconds")
    context_used: int = Field(..., description="Number of context messages used")


# AI Relationship Score Schemas


class AIRelationshipScoreResponse(BaseSchema):
    """Schema for AI relationship score data."""

    character_qiao_id: str = Field(..., description="Character external ID")
    score_order: int = Field(..., description="Score dimension order")
    score: int = Field(..., description="Current score value")
    score_start: int = Field(..., description="Starting score value")
    score_end: int = Field(..., description="Ending score value")
    score_position: int = Field(..., description="Per mille position (0-1000)")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AIRelationshipScoreUpdate(BaseModel):
    """Schema for updating AI relationship score."""

    score: int = Field(..., ge=0, le=1000, description="New score value")
