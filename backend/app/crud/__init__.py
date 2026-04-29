"""CRUD operations module.

This module imports all CRUD classes for database operations.
"""

# Admin CRUD
from .admin import admin_login_log, admin_operation_log, admin_user

# Base CRUD classes
from .base import CRUDBase, CRUDBaseWithQiaoId, CRUDBaseWithStatus, ImmutableCRUDBase
from .campaign import campaign, campaign_attribution

# Contact CRUD
from .contact import contact, contact_request
from .entitlement import (
    entitlement_reason_code,
    entitlement_type,
    user_entitlement_account,
    user_entitlement_ledger,
)
from .growth_reward import growth_reward_rule
from .invite import (
    invite_binding,
    invite_code,
    invite_event,
    invite_intake_log,
)

# LLM CRUD
from .llm import llm_config, llm_provider, llm_test_log

# Message CRUD
from .message import media_file, message
from .redeem import redeem_code, redeem_code_batch, redeem_code_claim

# System CRUD
from .system import (
    stats_ai_daily,
    stats_message_daily,
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
    "media_file",
    # AI - removed (using new data access layer)
    # Admin
    "admin_user",
    "admin_operation_log",
    "admin_login_log",
    # System
    "system_configs",
    "stats_user_daily",
    "stats_message_daily",
    "stats_ai_daily",
    # Invitation / Entitlement
    "invite_code",
    "invite_binding",
    "invite_event",
    "invite_intake_log",
    "campaign",
    "campaign_attribution",
    "growth_reward_rule",
    "redeem_code_batch",
    "redeem_code",
    "redeem_code_claim",
    "entitlement_type",
    "entitlement_reason_code",
    "user_entitlement_account",
    "user_entitlement_ledger",
    # LLM
    "llm_provider",
    "llm_config",
    "llm_test_log",
]
