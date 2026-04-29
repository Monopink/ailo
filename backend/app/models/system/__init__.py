"""System models module.

This module imports all system-related SQLAlchemy models.
"""

# Configuration models
# Alerting models
from .alerting import AlertEvent, AlertEventEntity
from .config import SystemConfig
from .runtime_observation import ClientRuntimeObservation

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
    # Alerting
    "AlertEvent",
    "AlertEventEntity",
    "ClientRuntimeObservation",
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
