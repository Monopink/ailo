"""Schemas for app page public APIs."""

from datetime import datetime

from pydantic import BaseModel, Field


class AppPageResponse(BaseModel):
    """Single app page payload for client display."""

    page_key: str = Field(..., description="Page key")
    page_category: int = Field(..., description="Page category (AppPageCategory value)")
    title: str = Field(..., description="Page title")
    locale: str = Field(..., description="Locale, currently fixed to zh-CN")
    content_rendered_format: str = Field(..., description="Rendered content format, currently html")
    content_rendered: str = Field(..., description="Rendered page body")
    updated_at: datetime = Field(..., description="Last update time")


class AppPageListResponse(BaseModel):
    """Batch app page payload."""

    items: list[AppPageResponse] = Field(..., description="App page items")
