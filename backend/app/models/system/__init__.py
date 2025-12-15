"""
System models module.

This module imports all system-related SQLAlchemy models.
"""

# Configuration models
from .config import SystemConfig

# Preset asset models
from .preset_asset import PresetAsset

# Statistics models
from .stats import (
    StatsAIDaily,
    StatsAIMonthly,
    StatsAIWeekly,
    StatsMessageDaily,
    StatsMessageMonthly,
    StatsMessageWeekly,
    StatsUserDaily,
    StatsUserMonthly,
    StatsUserWeekly,
)

# Export all system models
__all__ = [
    # Configuration
    "SystemConfig",
    # Preset assets
    "PresetAsset",
    # User statistics
    "StatsUserDaily",
    "StatsUserWeekly",
    "StatsUserMonthly",
    # Message statistics
    "StatsMessageDaily",
    "StatsMessageWeekly",
    "StatsMessageMonthly",
    # AI statistics
    "StatsAIDaily",
    "StatsAIWeekly",
    "StatsAIMonthly",
]
