"""
AI chat related schemas.

This module contains Pydantic schemas for AI chat interactions and relationship scoring.
"""

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema

# AI Chat Request/Response Schemas


class AIChatRequest(BaseModel):
    """Schema for AI chat request."""

    instance_qiao_id: str = Field(..., max_length=32, description="Instance external ID")
    message: str = Field(..., min_length=1, max_length=49, description="User message")
    context_limit: int = Field(10, ge=1, le=50, description="Maximum context messages to include")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="AI temperature setting")
    max_tokens: int | None = Field(None, ge=1, le=4000, description="Maximum response tokens")


class AIChatResponse(BaseSchema):
    """Schema for AI chat response."""

    message: str = Field(..., description="AI response message")
    instance_qiao_id: str = Field(..., description="Instance external ID")
    token_count: int | None = Field(None, description="Token consumption")
    response_time: int = Field(..., description="Response time in milliseconds")
    context_used: int = Field(..., description="Number of context messages used")
