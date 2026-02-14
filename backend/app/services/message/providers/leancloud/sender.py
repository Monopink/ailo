"""LeanCloud provider sender for timeline endpoint dispatch."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import MessageEndpoint, MessageHistory
from app.services.message.providers.base import MessageResult
from app.services.message.security.encryption import encrypt_for_transport
from app.type_defs import JSONDict

from . import service as leancloud_service


class LeanCloudTimelineSender:
    """Endpoint sender for LeanCloud transport."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def send_to_endpoint(
        self,
        *,
        endpoint: MessageEndpoint,
        message: MessageHistory,
    ) -> MessageResult:
        metadata = message.message_metadata if isinstance(message.message_metadata, dict) else {}
        raw_action = metadata.get("action")
        action: JSONDict | None = raw_action if isinstance(raw_action, dict) else None

        raw_notification_type = metadata.get("notification_type")
        notification_type = (
            raw_notification_type
            if isinstance(raw_notification_type, int)
            and not isinstance(raw_notification_type, bool)
            else None
        )

        encrypted_content, encryption_meta = encrypt_for_transport(message.content or "")
        extra_fields: dict[str, Any] = {
            "sent_time": int(message.sent_at.timestamp() * 1000) if message.sent_at else None,
        }
        if isinstance(message.msg_id_client, str) and message.msg_id_client:
            extra_fields["msg_id_client"] = message.msg_id_client
        extra_fields.update(encryption_meta)
        if notification_type is not None:
            extra_fields["notification_type"] = notification_type
        extra_fields = {key: value for key, value in extra_fields.items() if value is not None}

        return await leancloud_service.send_message_to_client(
            self._db,
            target_client_id=endpoint.target_key,
            from_qiao_id=message.from_qiao_id,
            to_qiao_id=message.to_qiao_id,
            conv_id=message.conversation_id,
            content=encrypted_content,
            message_type=int(message.message_type),
            action=action,
            extra_fields=extra_fields,
            msg_id=message.msg_id_server,
        )
