"""System CRUD operations module.

This module imports all system-related CRUD operations.
"""

# Configuration CRUD
from .config import CRUDSystemConfig, system_configs

# Statistics CRUD
from .stats import (
    CRUDStatsAI,
    CRUDStatsMessage,
    CRUDStatsUser,
    stats_ai_daily,
    stats_message_daily,
    stats_user_daily,
)

# Export all system CRUD classes and instances
__all__ = [
    # Classes
    "CRUDSystemConfig",
    "CRUDStatsUser",
    "CRUDStatsMessage",
    "CRUDStatsAI",
    # Instances
    "system_configs",
    "stats_user_daily",
    "stats_message_daily",
    "stats_ai_daily",
]
