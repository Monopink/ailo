"""
Convenience functions for common message sending scenarios.

These functions provide business-level abstractions over the core
timeline and notification sending functions.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.profile import profile as profile_crud
from app.enums import (
    MessageType,
    NotificationActionType,
    NotificationTarget,
    NotificationType,
)
from app.schemas.message import (
    ContactRequestNotificationData,
    NotificationAction,
    NotificationActionData,
)
from app.services.message.outbound.sender import send_notification, send_timeline_message
from app.services.profile.avatar import get_avatar_url
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def send_chat_info(
    db: AsyncSession,
    *,
    to_qiao_id: str,
    conversation_id: str,
    content: str,
    action: JSONDict | None = None,
) -> None:
    """
    Send CHAT_INFO message.

    Convenience function for sending chat interface informational messages.
    Caller should get text from CHAT_INFO_TEMPLATES if needed.

    Args:
        db: Database session
        to_qiao_id: Receiver's qiao_id
        conversation_id: Internal conversation identifier
        content: Message text (already resolved from template)

    Example:
        content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
        await send_chat_info(
            db, to_qiao_id=user_id, conversation_id=conversation_id, content=content
        )
    """
    await send_timeline_message(
        db=db,
        from_qiao_id="system",
        to_qiao_id=to_qiao_id,
        conv_id=conversation_id,
        content=content,
        message_type=MessageType.CHAT_INFO,
        action=action,
    )


async def send_contact_request_notification(
    db: AsyncSession,
    *,
    to_qiao_id: str,
    from_qiao_id: str,
    request_id: int,
    message: str,
) -> None:
    """
    Send contact request notification to user.

    Convenience function for sending contact request notifications.

    Args:
        db: Database session
        to_qiao_id: Receiver's qiao_id
        from_qiao_id: Sender's qiao_id
        request_id: Contact request ID
        message: Request message
    """
    # Get sender profile
    sender_profile = await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=from_qiao_id)

    # Profile data (keep None if not found)
    from_nickname = None
    from_avatar = None

    if sender_profile:
        from_nickname = sender_profile.nickname
        from_avatar = await get_avatar_url(sender_profile)
    else:
        logger.error(
            "sender_profile_not_found",
            from_qiao_id=from_qiao_id,
            request_id=request_id,
        )

    # Construct notification action data with type safety
    action_data = NotificationActionData(
        action=NotificationAction(
            type=NotificationActionType.NAVIGATE.value,
            target=NotificationTarget.CONTACT_REQUESTS.value,
        ),
        data=ContactRequestNotificationData(
            request_id=request_id,
            from_qiao_id=from_qiao_id,
            from_nickname=from_nickname or "",
            from_avatar=from_avatar or "",
            message=message or "",
        ),
    )

    # Send notification
    await send_notification(
        db=db,
        to_qiao_id=to_qiao_id,
        notification_type=NotificationType.CONTACT_REQUEST,
        action_data=action_data,
    )
