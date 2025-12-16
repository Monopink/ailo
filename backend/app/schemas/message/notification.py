"""
Notification schemas for type-safe notification data.

These schemas ensure notification payloads are validated at API boundaries
and provide strong typing throughout the notification system.
"""

from pydantic import BaseModel, Field


class NotificationAction(BaseModel):
    """Notification action data."""

    type: str = Field(..., description="Action type (e.g., 'navigate')")
    target: str = Field(..., description="Action target (e.g., 'contact_requests')")


class NotificationData(BaseModel):
    """Base notification data."""

    message: str = Field(default="", description="Fallback message for notification")


class ContactRequestNotificationData(NotificationData):
    """Data for contact request notifications."""

    request_id: int = Field(..., description="Contact request ID")
    from_qiao_id: str = Field(..., description="Sender's qiao_id")
    from_nickname: str = Field(..., description="Sender's nickname")
    from_avatar: str = Field(..., description="Sender's avatar URL")


class NotificationActionData(BaseModel):
    """
    Complete notification action data structure.

    This schema enforces the structure of notification payloads used across
    the system. Use specific data types (e.g., ContactRequestNotificationData)
    for the 'data' field when the notification type is known.
    """

    action: NotificationAction = Field(..., description="Action to perform")
    data: NotificationData = Field(..., description="Notification-specific data")
