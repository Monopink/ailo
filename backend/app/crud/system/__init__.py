"""
System CRUD operations module.

This module imports all system-related CRUD operations.
"""

# Configuration CRUD
from .config import CRUDSystemConfig, system_config

# Statistics CRUD
from .stats import (
    CRUDStatsUser,
    CRUDStatsRevenue,
    CRUDStatsMessage,
    CRUDStatsAI,
    stats_user_daily,
    stats_revenue_daily,
    stats_message_daily,
    stats_ai_daily,
)

# Export all system CRUD classes and instances
__all__ = [
    # Classes
    "CRUDSystemConfig",
    "CRUDStatsUser",
    "CRUDStatsRevenue",
    "CRUDStatsMessage",
    "CRUDStatsAI",
    # Instances
    "system_config",
    "stats_user_daily",
    "stats_revenue_daily",
    "stats_message_daily",
    "stats_ai_daily",
]
