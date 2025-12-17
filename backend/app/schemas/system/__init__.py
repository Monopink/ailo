"""
System schemas module.

This module imports all system-related Pydantic schemas.
"""

# Configuration schemas
from .config import (
    BatchConfigDelete,
    BatchConfigUpdate,
    ConfigValueResponse,
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigListResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)

# Statistics schemas
from .stats import (
    AIStatsBase,
    AIStatsDailyResponse,
    AIStatsMonthlyResponse,
    AIStatsWeeklyResponse,
    BaseStatsSchema,
    DashboardStats,
    MessageStatsBase,
    MessageStatsDailyResponse,
    MessageStatsMonthlyResponse,
    MessageStatsWeeklyResponse,
    RevenueStatsBase,
    RevenueStatsDailyResponse,
    RevenueStatsMonthlyResponse,
    RevenueStatsWeeklyResponse,
    StatsDateRange,
    StatsQuery,
    SystemHealthStats,
    UserStatsBase,
    UserStatsDailyResponse,
    UserStatsMonthlyResponse,
    UserStatsWeeklyResponse,
)

# Export all system schemas
__all__ = [
    # Configuration
    "SystemConfigBase",
    "SystemConfigCreate",
    "SystemConfigUpdate",
    "SystemConfigResponse",
    "SystemConfigListResponse",
    "ConfigValueResponse",
    "BatchConfigUpdate",
    "BatchConfigDelete",
    # Statistics
    "BaseStatsSchema",
    "UserStatsBase",
    "UserStatsDailyResponse",
    "UserStatsWeeklyResponse",
    "UserStatsMonthlyResponse",
    "RevenueStatsBase",
    "RevenueStatsDailyResponse",
    "RevenueStatsWeeklyResponse",
    "RevenueStatsMonthlyResponse",
    "MessageStatsBase",
    "MessageStatsDailyResponse",
    "MessageStatsWeeklyResponse",
    "MessageStatsMonthlyResponse",
    "AIStatsBase",
    "AIStatsDailyResponse",
    "AIStatsWeeklyResponse",
    "AIStatsMonthlyResponse",
    "StatsQuery",
    "StatsDateRange",
    "DashboardStats",
    "SystemHealthStats",
]
