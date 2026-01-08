"""System models module.

This module imports all system-related SQLAlchemy models.
"""

# Configuration models
from .config import SystemConfig

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
