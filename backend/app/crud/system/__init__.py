"""
System CRUD operations module.

This module imports all system-related CRUD operations.
"""

# Configuration CRUD
from .config import CRUDSystemConfig, system_configs

# Preset asset CRUD
from .preset_asset import CRUDPresetAsset, preset_assets

# Statistics CRUD
from .stats import (
    CRUDStatsAI,
    CRUDStatsMessage,
    CRUDStatsRevenue,
    CRUDStatsUser,
    stats_ai_daily,
    stats_message_daily,
    stats_revenue_daily,
    stats_user_daily,
)

# Export all system CRUD classes and instances
__all__ = [
    # Classes
    "CRUDSystemConfig",
    "CRUDPresetAsset",
    "CRUDStatsUser",
    "CRUDStatsRevenue",
    "CRUDStatsMessage",
    "CRUDStatsAI",
    # Instances
    "system_configs",
    "preset_assets",
    "stats_user_daily",
    "stats_revenue_daily",
    "stats_message_daily",
    "stats_ai_daily",
]
