"""Growth reward related enums."""

from enum import IntEnum


class GrowthRewardTargetRole(IntEnum):
    """Reward receiver role in reward rules."""

    ACTOR = 1
    INVITEE = 2
    INVITER = 3


class GrowthRewardScopeType(IntEnum):
    """Scope type enum for reward rule matching."""

    GLOBAL = 1
    CAMPAIGN = 2
    REDEEM_BATCH = 3


class GrowthRewardTriggerEvent(IntEnum):
    """Trigger event enum in growth reward rules."""

    INVITE_BIND_SUCCESS = 1
    INVITEE_SETUP_COMPLETED = 2
    CAMPAIGN_ATTRIBUTION_FIRST_TOUCH = 3
    REDEEM_CODE_CLAIM_SUCCESS = 4


class GrowthRewardRuleStatus(IntEnum):
    """Reward rule status."""

    ACTIVE = 1
    INACTIVE = 2
