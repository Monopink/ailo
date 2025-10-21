"""
AI chat related schemas.

This module contains Pydantic schemas for AI chat interactions and relationship scoring.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from schemas.common import BaseSchema


# AI Chat Request/Response Schemas


class AIChatRequest(BaseModel):
    """Schema for AI chat request."""

    character_qiao_id: str = Field(..., max_length=32, description="Character external ID")
    message: str = Field(..., min_length=1, max_length=49, description="User message")
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
    dimension_id: int = Field(..., description="Dimension ID")
    dimension_name: str = Field(..., description="Dimension name")
    score: int = Field(..., description="Current score value")
    position: int = Field(..., description="Per mille position (0-1000)")
    relationship_id: Optional[int] = Field(None, description="Current relationship type ID")
    relationship_display_name: Optional[str] = Field(None, description="Relationship display name")
    relationship_counts: Optional[Dict[str, Any]] = Field(None, description="Relationship usage counts")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class AIRelationshipScoreUpdate(BaseModel):
    """Schema for updating AI relationship score."""

    score: Optional[int] = Field(None, ge=0, le=1000, description="New score value")
    position: Optional[int] = Field(None, ge=0, le=1000, description="New position value")
    relationship_id: Optional[int] = Field(None, description="New relationship type ID")
    relationship_display_name: Optional[str] = Field(None, description="New relationship display name")
    relationship_counts: Optional[Dict[str, Any]] = Field(None, description="Updated relationship counts")
