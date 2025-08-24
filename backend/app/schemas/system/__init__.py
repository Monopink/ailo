"""
System schemas module.

This module imports all system-related Pydantic schemas.
"""

# Configuration schemas
from .config import (
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigResponse,
    SystemConfigListResponse,
    ConfigValueResponse,
    BatchConfigUpdate,
    BatchConfigDelete,
)

# Statistics schemas
from .stats import (
    BaseStatsSchema,
    UserStatsBase,
    UserStatsDailyResponse,
    UserStatsWeeklyResponse,
    UserStatsMonthlyResponse,
    RevenueStatsBase,
    RevenueStatsDailyResponse,
    RevenueStatsWeeklyResponse,
    RevenueStatsMonthlyResponse,
    MessageStatsBase,
    MessageStatsDailyResponse,
    MessageStatsWeeklyResponse,
    MessageStatsMonthlyResponse,
    AIStatsBase,
    AIStatsDailyResponse,
    AIStatsWeeklyResponse,
    AIStatsMonthlyResponse,
    StatsQuery,
    StatsDateRange,
    DashboardStats,
    SystemHealthStats,
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
