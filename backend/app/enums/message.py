"""Message system enums.

All enum values correspond to the integer values defined in the database schema.
"""

from enum import IntEnum, StrEnum


class MessageDirection(IntEnum):
    """Message direction (message_history.direction)."""

    INBOUND = 1
    OUTBOUND = 2


class MessageParticipantType(IntEnum):
    """Message sender/receiver type."""

    USER = 1
    AI = 2  # AI instance
    ADMIN = 3
    SYSTEM = 4


class MessageTransportProvider(IntEnum):
    """Message transport provider enum.

    Applies to:
    - message_history.inbound_provider
    - message_endpoints.provider
    - message_deliveries.provider
    """

    WEBSOCKET = 1
    LEANCLOUD = 2


class MessageEndpointScope(IntEnum):
    """Endpoint delivery scope (message_endpoints.endpoint_scope)."""

    USER = 1
    DEVICE = 2


class MessageDispatchOutboxType(IntEnum):
    """Dispatch outbox task type (message_dispatch_outbox.outbox_type)."""

    TIMELINE_FANOUT = 1


class MessageDispatchOutboxStatus(IntEnum):
    """Dispatch outbox task status (message_dispatch_outbox.status)."""

    PENDING = 1
    PROCESSING = 2
    DONE = 3
    FAILED = 4


class MessageType(IntEnum):
    """Message type classification (message_history.message_type)."""

    TEXT = 1
    TYPING_START = 2  # Typing indicator (user started typing)
    TYPING_END = 3  # Typing stopped indicator
    CHAT_INFO = 4  # Chat interface informational message
    NOTIFICATION = 9


class ChatInfoType(IntEnum):
    """Chat interface informational message subtypes."""

    CONTACT_ADDED = 1  # Contact has added you
    MESSAGE_BLOCKED = 2  # Message sent but blocked by recipient
    NOT_FRIEND = 3  # Recipient hasn't added you as contact


class NotificationType(IntEnum):
    """Notification message subtypes."""

    CONTACT_REQUEST = 1


class NotificationActionType(StrEnum):
    """Notification action types."""

    NAVIGATE = "navigate"  # Navigate to a page
    REFRESH = "refresh"  # Refresh data
    BADGE = "badge"  # Update badge count


class NotificationTarget(StrEnum):
    """Notification action targets."""

    CONTACT_REQUESTS = "contact_requests"  # Contact requests page
    CONTACTS = "contacts"  # Contacts list page


class NotificationStatus(IntEnum):
    """Notification push status."""

    SENT = 1
    FAILED = 2


class MessageDeliveryStatus(IntEnum):
    """Message delivery status (message_deliveries.status)."""

    PENDING = 1
    DISPATCHED = 2
    FAILED = 3


class EncryptionType(StrEnum):
    """Supported message encryption algorithms."""

    BASE64 = "base64"
    AES_256_GCM = "aes_256_gcm"


class EncryptionVersion(StrEnum):
    """Encryption schema version."""

    V1 = "v1"
