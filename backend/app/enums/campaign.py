"""Campaign-related enums."""

from enum import IntEnum


class CampaignStatus(IntEnum):
    """Campaign status for first-touch attribution."""

    ACTIVE = 1
    INACTIVE = 2
