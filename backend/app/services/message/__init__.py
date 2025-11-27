"""
Message service module.

Provides unified message handling with clear separation between:
- Business layer (inbound, outbound, processing, storage, security)
- Transport layer (providers)
"""

from .inbound.router import route_message
from .monitoring.health import check_message_service_health
from .outbound.helpers import send_chat_info, send_contact_request_notification

# Export commonly used functions
from .outbound.sender import send_message, send_notification

__all__ = [
    "send_message",
    "send_notification",
    "send_chat_info",
    "send_contact_request_notification",
    "route_message",
    "check_message_service_health",
]
