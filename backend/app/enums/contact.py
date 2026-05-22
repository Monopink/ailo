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
    ALL_TEMPLATES_ALREADY_USED = "ALL_TEMPLATES_ALREADY_USED"
    MANUAL_PROVISION_REQUIRED = "MANUAL_PROVISION_REQUIRED"


class ContactRequestRetryMode(StrEnum):
    """Retry mode enum for admin contact request retry APIs."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class ContactRequestRetryResultStatus(StrEnum):
    """Result status enum for contact_request_retry_attempts.result_status."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class ContactRequestRetryFailureCode(StrEnum):
    """Failure code enum for contact_request_retry_attempts.result_failure_code."""

    RETRY_ATTEMPT_NOT_FOUND = "RETRY_ATTEMPT_NOT_FOUND"
    RETRY_REJECTED = "RETRY_REJECTED"
    RETRY_EXCEPTION = "RETRY_EXCEPTION"
    AI_CONTACT_LIMIT_REACHED = "AI_CONTACT_LIMIT_REACHED"


class ContactRequestRetryRuleCode(StrEnum):
    """Rule/check code enum used by retry precheck and execute."""

    REQUEST_RETRYABLE = "REQUEST_RETRYABLE"
    REQUEST_AI_TYPE_PRESENT = "REQUEST_AI_TYPE_PRESENT"
    ACTIVE_TEMPLATE_EXISTS = "ACTIVE_TEMPLATE_EXISTS"
    AVAILABLE_TEMPLATE_EXISTS = "AVAILABLE_TEMPLATE_EXISTS"
    REQUEST_AI_TYPE_MISSING = "REQUEST_AI_TYPE_MISSING"
    AUTO_NO_ACTIVE_TEMPLATE = "AUTO_NO_ACTIVE_TEMPLATE"
    AUTO_NO_SELECTABLE_TEMPLATE = "AUTO_NO_SELECTABLE_TEMPLATE"
    MANUAL_AI_TYPE_PRESENT = "MANUAL_AI_TYPE_PRESENT"
    MANUAL_AI_TYPE_MATCH_REQUEST = "MANUAL_AI_TYPE_MATCH_REQUEST"
    TEMPLATE_FOUND = "TEMPLATE_FOUND"
    TEMPLATE_USED_BY_USER = "TEMPLATE_USED_BY_USER"
    TEMPLATE_ALREADY_USED_BY_USER = "TEMPLATE_ALREADY_USED_BY_USER"
    TEMPLATE_TYPE_MATCH_SELECTED_AI_TYPE = "TEMPLATE_TYPE_MATCH_SELECTED_AI_TYPE"
    TEMPLATE_TYPE_MISMATCH = "TEMPLATE_TYPE_MISMATCH"
    TEMPLATE_STATUS_ACTIVE = "TEMPLATE_STATUS_ACTIVE"
    TEMPLATE_STATUS_NON_ACTIVE = "TEMPLATE_STATUS_NON_ACTIVE"
