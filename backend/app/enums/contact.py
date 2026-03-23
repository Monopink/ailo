"""Contact management enums.

All enum values correspond to the integer values defined in the database schema.
"""

from enum import IntEnum, StrEnum


class ContactType(IntEnum):
    """Contact type classification (contacts.contact_type)."""

    USER = 1
    AI = 2  # AI instance
    OFFICIAL = 3


class ContactSource(IntEnum):
    """Contact creation source (contacts.source)."""

    UNKNOWN = 0
    SEARCH = 1
    ADMIN = 2
    SYSTEM = 3
    RECOMMEND = 4
    DISCOVERY = 5
    CONTACT_REQUEST = 6


class AvatarDisplayMode(IntEnum):
    """Contact avatar display mode (contacts.avatar_display_mode)."""

    ORIGINAL = 1
    CUSTOM = 2


class ContactRequestSource(IntEnum):
    """Contact request source (contact_requests.source)."""

    SEARCH = 1
    ADMIN = 2
    SYSTEM = 3
    RECOMMEND = 4


class ContactRequestStatus(IntEnum):
    """Contact request status (contact_requests.status)."""

    PENDING = 1
    ACCEPTED = 2
    IGNORED = 3  # Ignored (AI decided not to accept, or user actively ignored)
    PROCESSING = 8  # Processing by worker (prevents duplicate processing)
    FAILED = 9  # Processing failed due to system error (future explicit rejection support)


class ContactRequestFailureCode(StrEnum):
    """Stable failure codes for contact requests (contact_requests.failure_code)."""

    NO_TEMPLATE_AVAILABLE = "NO_TEMPLATE_AVAILABLE"
    MANUAL_PROVISION_REQUIRED = "MANUAL_PROVISION_REQUIRED"
