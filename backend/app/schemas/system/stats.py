"""
System statistics related schemas.

This module contains Pydantic schemas for various system statistics.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field
from schemas.common import BaseSchema

# Base Statistics Schema


class BaseStatsSchema(BaseSchema):
    """Base statistics schema."""

    stat_date: date = Field(..., description="Statistics date")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


# User Statistics Schemas


class UserStatsBase(BaseStatsSchema):
    """Base user statistics schema."""

    total_users: int = Field(..., ge=0, description="Total user count")
    new_users: int = Field(..., ge=0, description="New user count")
    active_users: int = Field(..., ge=0, description="Active user count")
    subscriptions: int = Field(..., ge=0, description="Total subscription count")
    new_subscriptions: int = Field(..., ge=0, description="New subscription count")
    canceled_subscriptions: int = Field(..., ge=0, description="Canceled subscription count")


class UserStatsDailyResponse(UserStatsBase):
    """Schema for daily user statistics response."""

    pass


class UserStatsWeeklyResponse(UserStatsBase):
    """Schema for weekly user statistics response."""

    pass


class UserStatsMonthlyResponse(UserStatsBase):
    """Schema for monthly user statistics response."""

    pass


# Revenue Statistics Schemas


class RevenueStatsBase(BaseStatsSchema):
    """Base revenue statistics schema."""

    total_revenue: float = Field(..., ge=0, description="Total revenue")
    orders_count: int = Field(..., ge=0, description="Order count")
    avg_order_amount: float = Field(..., ge=0, description="Average order amount")
    refund_amount: float = Field(..., ge=0, description="Refund amount")


class RevenueStatsDailyResponse(RevenueStatsBase):
    """Schema for daily revenue statistics response."""

    pass


class RevenueStatsWeeklyResponse(RevenueStatsBase):
    """Schema for weekly revenue statistics response."""

    pass


class RevenueStatsMonthlyResponse(RevenueStatsBase):
    """Schema for monthly revenue statistics response."""

    pass


# Message Statistics Schemas


class MessageStatsBase(BaseStatsSchema):
    """Base message statistics schema."""

    total_messages: int = Field(..., ge=0, description="Total message count")
    avg_messages_per_user: float = Field(..., ge=0, description="Average messages per user")
    active_conversations: int = Field(..., ge=0, description="Active conversation count")


class MessageStatsDailyResponse(MessageStatsBase):
    """Schema for daily message statistics response."""

    pass


class MessageStatsWeeklyResponse(MessageStatsBase):
    """Schema for weekly message statistics response."""

    pass


class MessageStatsMonthlyResponse(MessageStatsBase):
    """Schema for monthly message statistics response."""

    pass


# AI Statistics Schemas


class AIStatsBase(BaseStatsSchema):
    """Base AI statistics schema."""

    ai_instances: int = Field(..., ge=0, description="Total AI instance count")
    active_ai_instances: int = Field(..., ge=0, description="Active AI instance count")
    ai_requests_count: int = Field(..., ge=0, description="AI request count")
    avg_ai_requests_per_user: float = Field(..., ge=0, description="Average AI requests per user")


class AIStatsDailyResponse(AIStatsBase):
    """Schema for daily AI statistics response."""

    pass


class AIStatsWeeklyResponse(AIStatsBase):
    """Schema for weekly AI statistics response."""

    pass


class AIStatsMonthlyResponse(AIStatsBase):
    """Schema for monthly AI statistics response."""

    pass


# Statistics Query Schemas


class StatsQuery(BaseModel):
    """Schema for statistics query parameters."""

    start_date: Optional[date] = Field(None, description="Start date for statistics")
    end_date: Optional[date] = Field(None, description="End date for statistics")
    limit: int = Field(30, ge=1, le=365, description="Maximum number of records")


class StatsDateRange(BaseModel):
    """Schema for statistics date range."""

    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")


# Dashboard Statistics


class DashboardStats(BaseSchema):
    """Schema for dashboard statistics summary."""

    total_users: int = Field(..., description="Total user count")
    active_users: int = Field(..., description="Active user count")
    total_messages: int = Field(..., description="Total message count")
    total_ai_instances: int = Field(..., description="Total AI instance count")
    daily_new_users: int = Field(..., description="Daily new user count")
    daily_messages: int = Field(..., description="Daily message count")
    daily_revenue: float = Field(..., description="Daily revenue")
    system_uptime: str = Field(..., description="System uptime")


# System Health Statistics


class SystemHealthStats(BaseSchema):
    """Schema for system health statistics."""

    cpu_usage: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_usage: float = Field(..., ge=0, le=100, description="Memory usage percentage")
    disk_usage: float = Field(..., ge=0, le=100, description="Disk usage percentage")
    database_connections: int = Field(..., ge=0, description="Active database connections")
    redis_connections: Optional[int] = Field(None, ge=0, description="Active Redis connections")
    response_time: float = Field(..., ge=0, description="Average response time in milliseconds")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    last_updated: datetime = Field(..., description="Last update time")
