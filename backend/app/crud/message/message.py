"""Message CRUD operations.

This module contains CRUD operations for message history and conversations.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import MessageStatus, MessageType
from app.models.message import MessageHistory


class _MessageSchema(BaseModel):
    """Dummy schema for read-only message CRUD operations.

    MessageHistory is read-only from CRUD perspective (created via IM SDK events),
    so create/update operations are not used.
    """


class CRUDMessage(CRUDBase[MessageHistory, _MessageSchema, _MessageSchema]):
    """CRUD operations for MessageHistory model."""

    async def get_by_server_id(
        self, db: AsyncSession, *, msg_id_server: str
    ) -> MessageHistory | None:
        """Get message by server ID."""
        result = await db.execute(
            select(self.model).where(self.model.msg_id_server == msg_id_server)
        )
        return result.scalar_one_or_none()

    async def get_by_client_id(
        self, db: AsyncSession, *, msg_id_client: str
    ) -> MessageHistory | None:
        """Get message by client ID."""
        result = await db.execute(
            select(self.model).where(self.model.msg_id_client == msg_id_client)
        )
        return result.scalar_one_or_none()

    async def get_by_conversation_and_client_id(
        self, db: AsyncSession, *, conversation_id: str, msg_id_client: str
    ) -> MessageHistory | None:
        """Get message by conversation + client ID (idempotency check)."""
        result = await db.execute(
            select(self.model).where(
                self.model.conversation_id == conversation_id,
                self.model.msg_id_client == msg_id_client,
            )
        )
        return result.scalar_one_or_none()

    async def get_conversation_messages(
        self,
        db: AsyncSession,
        *,
        conversation_id: str,
        before_time: datetime | None = None,
        after_time: datetime | None = None,
        message_types: list[MessageType] | None = None,
        limit: int = 50,
    ) -> list[MessageHistory]:
        """Get conversation messages with filtering."""
        conditions = [self.model.conversation_id == conversation_id]

        if before_time:
            conditions.append(self.model.created_at < before_time)
        if after_time:
            conditions.append(self.model.created_at > after_time)
        if message_types:
            conditions.append(self.model.message_type.in_(message_types))

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_conversations(
        self, db: AsyncSession, *, user_qiao_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get user's conversation list with last message."""
        # This would typically involve a complex query with subqueries
        # For now, return a simplified version
        result = await db.execute(
            select(self.model.conversation_id, func.max(self.model.created_at))
            .where(
                or_(self.model.from_qiao_id == user_qiao_id, self.model.to_qiao_id == user_qiao_id)
            )
            .group_by(self.model.conversation_id)
            .order_by(desc(func.max(self.model.created_at)))
            .limit(limit)
        )
        return [{"conversation_id": row[0], "last_message_time": row[1]} for row in result.all()]

    async def get_unread_count(
        self,
        db: AsyncSession,
        *,
        conversation_id: str,
        user_qiao_id: str,
        last_read_time: datetime | None = None,
    ) -> int:
        """Get unread message count for a conversation."""
        conditions = [
            self.model.conversation_id == conversation_id,
            self.model.to_qiao_id == user_qiao_id,
            self.model.status == MessageStatus.DELIVERED,
        ]

        if last_read_time:
            conditions.append(self.model.created_at > last_read_time)

        result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        count = result.scalar()
        return count if count is not None else 0

    async def update_message_status(
        self, db: AsyncSession, *, msg_id_server: str, status: MessageStatus
    ) -> MessageHistory | None:
        """Update message status."""
        message = await self.get_by_server_id(db, msg_id_server=msg_id_server)
        if message:
            message.status = status
            db.add(message)
            await db.commit()
            await db.refresh(message)
        return message

    async def batch_update_status(
        self, db: AsyncSession, *, msg_ids: list[str], status: MessageStatus
    ) -> int:
        """Batch update message status."""
        result = await db.execute(select(self.model).where(self.model.msg_id_server.in_(msg_ids)))
        messages = result.scalars().all()

        count = 0
        for message in messages:
            message.status = status
            db.add(message)
            count += 1

        await db.commit()
        return count

    async def search_messages(
        self, db: AsyncSession, *, conversation_id: str, query: str, limit: int = 20
    ) -> list[MessageHistory]:
        """Search messages in a conversation."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.conversation_id == conversation_id,
                    self.model.message_type == MessageType.TEXT,
                    self.model.content.ilike(f"%{query}%"),
                )
            )
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())


# Create instance
message = CRUDMessage(MessageHistory)
