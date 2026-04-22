"""Entitlement enums."""

from enum import StrEnum


class EntitlementSourceType(StrEnum):
    """Source type enum for entitlement ledger records."""

    SYSTEM_INITIAL = "system_initial"
    INVITE_BIND_INVITEE = "invite_bind_invitee"
    INVITE_BIND_INVITER = "invite_bind_inviter"
    CAMPAIGN_ATTRIBUTION = "campaign_attribution"
    REDEEM_CODE_CLAIM = "redeem_code_claim"
    CONTACT_AI_SLOT = "contact_ai_slot"
    ADMIN_MANUAL_GRANT = "admin_manual_grant"
    ADMIN_MANUAL_ADJUST = "admin_manual_adjust"
