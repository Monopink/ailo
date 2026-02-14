"""WebSocket provider sender for timeline endpoint dispatch."""

from __future__ import annotations

from typing import Any

from app.models.message import MessageEndpoint, MessageHistory
from app.services.message.providers.base import MessageResult
from app.services.message.websocket.manager import ws_manager


class WebSocketTimelineSender:
    """Endpoint sender for websocket transport."""

    async def send_to_endpoint(
        self,
        *,
        endpoint: MessageEndpoint,
        message: MessageHistory,
    ) -> MessageResult:
        payload: dict[str, Any] = {
            "event_type": "message",
            "message": {
                "msg_id_server": message.msg_id_server,
                "msg_id_client": message.msg_id_client,
                "conversation_id": message.conversation_id,
                "from_qiao_id": message.from_qiao_id,
                "to_qiao_id": message.to_qiao_id,
                "message_type": message.message_type,
                "content": message.content or "",
                "client_sent_time_ms": int(message.client_sent_at.timestamp() * 1000)
                if message.client_sent_at
                else None,
                "sent_time_ms": int(message.sent_at.timestamp() * 1000) if message.sent_at else 0,
                "metadata": message.message_metadata
                if isinstance(message.message_metadata, dict)
                else {},
            },
        }
        frame = {
            "type": "event",
            "ws_frame_id": f"evt_{message.msg_id_server}",
            "payload": payload,
        }

        ok = await ws_manager.send_json(int(endpoint.id), frame)
        if not ok:
            await ws_manager.unregister(int(endpoint.id))
            return MessageResult(
                success=False,
                error_code="WS_SEND_FAILED",
                error_message="WebSocket endpoint send failed",
            )
        return MessageResult(success=True)
