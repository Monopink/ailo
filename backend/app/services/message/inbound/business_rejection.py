"""Inbound business rejection rules.

This module centralizes "business-layer failures" that happen after the server
has accepted an inbound user message, but before it is allowed to enter any
downstream pipelines (e.g., AI buffering / LLM).

Business failures are reported back to clients through a CHAT_INFO timeline
message with `action.type=mark_message_failed` (see docs/spec/message/special-types.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageType
from app.enums.templates import CHAT_INFO_TEMPLATES, ChatInfoType
from app.models.ai.instance import AIInstance
from app.models.contact import Contact
from app.services.message.schemas import InboundMessageEvent
from app.services.message.security.validation import message_validation_service
from app.services.security.rate_limiter import check_message_rate_limit
from app.services.system_config import get_config_int
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BusinessRejection:
    """Represents a business rejection that should be pushed to the timeline."""

    content: str
    action: JSONDict


async def maybe_reject_inbound_message(
    db: AsyncSession,
    *,
    event: InboundMessageEvent,
    contact: Contact,
    is_for_ai: bool,
) -> BusinessRejection | None:
    """
    Check if the inbound message should be business-rejected.

    Notes:
    - Only TEXT messages can be rejected by these rules.
    - Rejection MUST NOT enter AI buffer/LLM pipelines.
    - Rejection is expressed as a CHAT_INFO message with an action.
    """
    if event.message_type != MessageType.TEXT:
        return None

    # 1) Length limit (do not count toward rate limiting).
    max_len = await get_config_int(db, key="max_message_length_chars")
    if len(event.content) > max_len:
        return BusinessRejection(
            content=f"消息字数超过限制（最多{max_len}字）",
            action={
                "type": "mark_message_failed",
                "target_msg_id": event.msg_id_client,
                "reason": "MESSAGE_TOO_LONG",
                "max_message_length_chars": max_len,
            },
        )

    # 2) Permission validation (AI conversations only; do not count toward rate limiting).
    if is_for_ai:
        instance = await _get_instance_for_contact(db, contact=contact)
        validation_result = await message_validation_service.validate_message_permission(
            db=db,
            from_qiao_id=event.from_qiao_id,
            instance=instance,
            contact=contact,
        )
        if not validation_result.allowed:
            template_key = validation_result.chat_info_type or ChatInfoType.MESSAGE_BLOCKED
            content = CHAT_INFO_TEMPLATES.get(template_key)
            if not content:
                logger.error(
                    "chat_info_template_missing",
                    chat_info_type=int(template_key),
                    conversation_id=contact.conversation_id,
                )
                content = "消息已发出，但对方拒收了"

            reason = _reason_from_chat_info_type(template_key)
            return BusinessRejection(
                content=content,
                action={
                    "type": "mark_message_failed",
                    "target_msg_id": event.msg_id_client,
                    "reason": reason,
                },
            )

    # 3) Rate limiting (applies to accepted TEXT attempts).
    allowed, _error_code, retry_after_seconds = await check_message_rate_limit(
        identifier=event.from_qiao_id,
        db=db,
    )
    if not allowed:
        retry_suffix = (
            f"（{retry_after_seconds}秒后再试）"
            if isinstance(retry_after_seconds, int) and retry_after_seconds > 0
            else ""
        )
        action: JSONDict = {
            "type": "mark_message_failed",
            "target_msg_id": event.msg_id_client,
            "reason": "MESSAGE_RATE_LIMITED",
        }
        if isinstance(retry_after_seconds, int) and retry_after_seconds > 0:
            action["retry_after_seconds"] = retry_after_seconds
        return BusinessRejection(
            content=f"发送太频繁，请稍后再试{retry_suffix}",
            action=action,
        )

    return None


async def _get_instance_for_contact(db: AsyncSession, *, contact: Contact) -> AIInstance:
    result = await db.execute(select(AIInstance).where(AIInstance.id == contact.contact_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        logger.error(
            "ai_instance_missing_for_contact",
            conversation_id=contact.conversation_id,
            contact_id=contact.contact_id,
            contact_qiao_id=contact.contact_qiao_id,
        )
        raise ValueError("AI instance not found for contact.")
    return instance


def _reason_from_chat_info_type(chat_info_type: ChatInfoType) -> str:
    mapping: dict[ChatInfoType, str] = {
        ChatInfoType.MESSAGE_BLOCKED: "MESSAGE_BLOCKED",
        ChatInfoType.NOT_FRIEND: "NOT_FRIEND",
        ChatInfoType.CONTACT_ADDED: "CONTACT_ADDED",
    }
    return mapping[chat_info_type]
