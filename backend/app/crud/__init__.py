"""
CRUD operations module.

This module imports all CRUD classes for database operations.
"""

# Base CRUD classes
from .base import CRUDBase, CRUDBaseWithQiaoId, CRUDBaseWithStatus, ImmutableCRUDBase

# User CRUD
from .user import user, user_token, login_record

# Contact CRUD
from .contact import contact, contact_request

# Message CRUD
from .message import message, message_failure, media_file

# AI CRUD - removed (using new data access layer)

# Admin CRUD
from .admin import admin_user, admin_operation_log, admin_login_log

# System CRUD
from .system import (
    system_configs,
    stats_user_daily,
    stats_revenue_daily,
    stats_message_daily,
    stats_ai_daily,
)

# LLM CRUD
from .llm import llm_provider, llm_config, llm_test_log

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
