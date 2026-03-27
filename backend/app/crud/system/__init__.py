"""System CRUD operations module.

This module imports all system-related CRUD operations.
"""

# Configuration CRUD
# Alerting CRUD
from .alerting import CRUDAlertEvent, alert_events
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
    "CRUDAlertEvent",
    "CRUDStatsUser",
    "CRUDStatsMessage",
    "CRUDStatsAI",
    # Instances
    "system_configs",
    "alert_events",
    "stats_user_daily",
    "stats_message_daily",
    "stats_ai_daily",
]
