"""
CRUD operations module.

This module imports all CRUD classes for database operations.
"""

# Base CRUD classes
from .base import CRUDBase, CRUDBaseWithQiaoId, CRUDBaseWithStatus

# User CRUD
from .user import user, user_session, login_record

# Contact CRUD
from .contact import contact, contact_request

# Message CRUD
from .message import message, message_failure, media_file, emoticon

# AI CRUD
from .ai import (
    ai_character,
    ai_personality,
    ai_style,
    ai_info_template,
    ai_profile_template,
    ai_context,
    ai_request_log,
)

# Admin CRUD
from .admin import admin_user, admin_operation_log, admin_login_log

# System CRUD
from .system import (
    system_config,
    stats_user_daily,
    stats_revenue_daily,
    stats_message_daily,
    stats_ai_daily,
)

# Export all CRUD instances
__all__ = [
    # Base classes
    "CRUDBase",
    "CRUDBaseWithQiaoId",
    "CRUDBaseWithStatus",
    # User
    "user",
    "user_session",
    "login_record",
    # Contact
    "contact",
    "contact_request",
    # Message
    "message",
    "message_failure",
    "media_file",
    "emoticon",
    # AI - removed (using new data access layer)
    # Admin
    "admin_user",
    "admin_operation_log",
    "admin_login_log",
    # System
    "system_config",
    "stats_user_daily",
    "stats_revenue_daily",
    "stats_message_daily",
    "stats_ai_daily",
]
