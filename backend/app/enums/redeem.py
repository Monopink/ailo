"""Redeem code related enums."""

from enum import IntEnum


class RedeemCodeBatchStatus(IntEnum):
    """Redeem code batch status."""

    ACTIVE = 1
    INACTIVE = 2


class RedeemCodeMode(IntEnum):
    """Redeem code mode."""

    ONE_TIME = 1
    SHARED = 2


class RedeemCodeStatus(IntEnum):
    """Redeem code status."""

    ACTIVE = 1
    INACTIVE = 2
