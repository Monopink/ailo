"""
CRUD operations module.

This module imports all CRUD classes for database operations.
"""

# Admin CRUD
from .admin import admin_login_log, admin_operation_log, admin_user

# Base CRUD classes
from .base import CRUDBase, CRUDBaseWithQiaoId, CRUDBaseWithStatus, ImmutableCRUDBase

# Contact CRUD
from .contact import contact, contact_request

# LLM CRUD
from .llm import llm_config, llm_provider, llm_test_log

# Message CRUD
from .message import media_file, message, message_failure

# System CRUD
from .system import (
    stats_ai_daily,
    stats_message_daily,
    stats_revenue_daily,
    stats_user_daily,
    system_configs,
)

# User CRUD
from .user import login_record, user, user_token

# Export all CRUD instances
__all__ = [
    # Base classes
    "CRUDBase",
    "CRUDBaseWithQiaoId",
    "CRUDBaseWithStatus",
    "ImmutableCRUDBase",
    # User
    "user",
    "user_token",
    "login_record",
    # Contact
    "contact",
    "contact_request",
    # Message
    "message",
    "message_failure",
    "media_file",
    # AI - removed (using new data access layer)
    # Admin
    "admin_user",
    "admin_operation_log",
    "admin_login_log",
    # System
    "system_configs",
    "stats_user_daily",
    "stats_revenue_daily",
    "stats_message_daily",
    "stats_ai_daily",
    # LLM
    "llm_provider",
    "llm_config",
    "llm_test_log",
]
