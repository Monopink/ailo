"""WebSocket inbound payload adapter for unified message events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from app.enums import MessageTransportProvider, MessageType
from app.services.message.schemas import EventMetadata, InboundMessageEvent

TypingState = Literal["start", "end"]


class WebSocketPayloadValidationError(ValueError):
    """Raised when websocket frame payload is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(slots=True)
class WebSocketSendMessagePayload:
    """Normalized payload for `send_message` websocket frame."""

    msg_id_client: str
    conversation_id: str
    content: str
    supports_typing: bool
    client_sent_time_ms: int | None


@dataclass(slots=True)
class WebSocketTypingPayload:
    """Normalized payload for `typing` websocket frame."""

    msg_id_client: str
    conversation_id: str
    typing_state: TypingState
    supports_typing: bool
    client_sent_time_ms: int | None


def _normalize_client_sent_time_ms(raw: object) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return None


def _normalize_supports_typing(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return bool(raw)


def parse_send_message_payload(payload: Mapping[str, object]) -> WebSocketSendMessagePayload:
    """Validate websocket `send_message` payload and normalize business fields."""
    msg_id_client = payload.get("msg_id_client")
    conversation_id = payload.get("conversation_id")
    content = payload.get("content", "")
    supports_typing = payload.get("supports_typing", True)
    client_sent_time_ms = payload.get("client_sent_time_ms")

    if not isinstance(msg_id_client, str) or not msg_id_client:
        raise WebSocketPayloadValidationError("msg_id_client 缺失")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise WebSocketPayloadValidationError("conversation_id 缺失")
    if not isinstance(content, str):
        raise WebSocketPayloadValidationError("content 格式错误")

    return WebSocketSendMessagePayload(
        msg_id_client=msg_id_client,
        conversation_id=conversation_id,
        content=content,
        supports_typing=_normalize_supports_typing(supports_typing),
        client_sent_time_ms=_normalize_client_sent_time_ms(client_sent_time_ms),
    )


def parse_typing_payload(payload: Mapping[str, object]) -> WebSocketTypingPayload:
    """Validate websocket `typing` payload and normalize business fields."""
    msg_id_client = payload.get("msg_id_client")
    conversation_id = payload.get("conversation_id")
    typing_state = payload.get("typing_state")
    supports_typing = payload.get("supports_typing", True)
    client_sent_time_ms = payload.get("client_sent_time_ms")

    if not isinstance(conversation_id, str) or not conversation_id:
        raise WebSocketPayloadValidationError("conversation_id 缺失")
    if not isinstance(typing_state, str) or typing_state not in {"start", "end"}:
        raise WebSocketPayloadValidationError("typing_state 无效")
    if not isinstance(msg_id_client, str) or not msg_id_client:
        raise WebSocketPayloadValidationError("msg_id_client 缺失")

    return WebSocketTypingPayload(
        msg_id_client=msg_id_client,
        conversation_id=conversation_id,
        typing_state=cast(TypingState, typing_state),
        supports_typing=_normalize_supports_typing(supports_typing),
        client_sent_time_ms=_normalize_client_sent_time_ms(client_sent_time_ms),
    )


def build_send_message_event(
    *,
    payload: WebSocketSendMessagePayload,
    from_qiao_id: str,
    to_qiao_id: str,
    inbound_device_id: UUID,
    sent_at_ms: int,
) -> InboundMessageEvent:
    """Convert normalized websocket send payload to unified inbound event."""
    return InboundMessageEvent(
        message_type=MessageType.TEXT,
        conversation_id=payload.conversation_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        content=payload.content,
        sent_at_ms=sent_at_ms,
        client_sent_time_ms=payload.client_sent_time_ms,
        msg_id_client=payload.msg_id_client,
        msg_id_provider_inbound=None,
        supports_typing=payload.supports_typing,
        metadata=EventMetadata(),
        inbound_provider=MessageTransportProvider.WEBSOCKET,
        inbound_device_id=str(inbound_device_id),
    )


def build_typing_event(
    *,
    payload: WebSocketTypingPayload,
    from_qiao_id: str,
    to_qiao_id: str,
    inbound_device_id: UUID,
    sent_at_ms: int,
) -> InboundMessageEvent:
    """Convert normalized websocket typing payload to unified inbound event."""
    message_type = (
        MessageType.TYPING_START if payload.typing_state == "start" else MessageType.TYPING_END
    )
    return InboundMessageEvent(
        message_type=message_type,
        conversation_id=payload.conversation_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        content="",
        sent_at_ms=sent_at_ms,
        client_sent_time_ms=payload.client_sent_time_ms,
        msg_id_client=payload.msg_id_client,
        msg_id_provider_inbound=None,
        supports_typing=payload.supports_typing,
        metadata=EventMetadata(),
        inbound_provider=MessageTransportProvider.WEBSOCKET,
        inbound_device_id=str(inbound_device_id),
    )
