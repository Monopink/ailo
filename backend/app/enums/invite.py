"""Invite code and invite event enums."""

from enum import IntEnum, StrEnum


class InviteCodeStatus(IntEnum):
    """Invite code status (invite_codes.status)."""

    ACTIVE = 1
    INACTIVE = 2


class InviteEventType(IntEnum):
    """Invite event type (invite_events.event_type)."""

    OPEN = 1
    RESOLVE_VALID = 2
    BIND_SUCCESS = 3
    COPY_COMMAND = 4
    SHARE_WECHAT = 5


class InviteResolveCodeType(StrEnum):
    """Cross-boundary code type strings for API payloads."""

    USER = "user"
