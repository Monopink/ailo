from typing import Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from models.message import MessageHistory
from utils.logging import get_logger
from .base import CRUDBase

logger = get_logger(__name__)


class CRUDMessage(CRUDBase[MessageHistory]):
    """CRUD operations for message processing."""

    async def save_message(self, db: AsyncSession, message: Dict[str, Any]) -> MessageHistory:
        """Save a message to the database"""
        try:
            message_record = MessageHistory(
                message_id=message.get("message_id"),
                message_id_client=message.get("message_id_client"),
                from_entity=message.get("from_entity"),
                to_entity=message.get("to_entity"),
                content=message.get("content"),
                message_type=message.get("message_type", "chat"),
                message_service=message.get("message_service"),
                message_time=message.get("message_time"),  # Service layer already processed
                status=message.get("status", "sent"),
                message_metadata=message.get("message_metadata"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            db.add(message_record)
            await db.commit()
            await db.refresh(message_record)
            return message_record

        except Exception as e:
            await db.rollback()
            logger.error("message_save_failed", error=str(e))
            raise

    async def get_messages_between_entities(
        self,
        db: AsyncSession,
        entity1: str,
        entity2: str,
        limit: int = 10,
        order_by_created: bool = False,  # True=created_at, False=message_time
    ) -> List[MessageHistory]:
        """Get messages between two entities with flexible ordering."""
        order_field = MessageHistory.created_at if order_by_created else MessageHistory.message_time

        result = await db.execute(
            select(MessageHistory)
            .where(
                or_(
                    and_(MessageHistory.from_entity == entity1, MessageHistory.to_entity == entity2),
                    and_(MessageHistory.from_entity == entity2, MessageHistory.to_entity == entity1),
                )
            )
            .order_by(desc(order_field))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_conversation_history(
        self, db: AsyncSession, entities: List[str], limit: int = 50
    ) -> List[MessageHistory]:
        """Get conversation history involving multiple entities."""
        if len(entities) < 2:
            return []

        # Build conditions for all entity combinations
        conditions = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                conditions.append(
                    and_(MessageHistory.from_entity == entities[i], MessageHistory.to_entity == entities[j])
                )
                conditions.append(
                    and_(MessageHistory.from_entity == entities[j], MessageHistory.to_entity == entities[i])
                )

        result = await db.execute(
            select(MessageHistory)
            .where(or_(*conditions))
            .order_by(desc(MessageHistory.message_time))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_latest_messages_by_entity(
        self, db: AsyncSession, entity_id: str, limit: int = 20
    ) -> List[MessageHistory]:
        """Get latest messages involving a specific entity."""
        result = await db.execute(
            select(MessageHistory)
            .where(or_(MessageHistory.from_entity == entity_id, MessageHistory.to_entity == entity_id))
            .order_by(desc(MessageHistory.message_time))
            .limit(limit)
        )
        return result.scalars().all()

    async def update_message_status(self, db: AsyncSession, message_id_client: str, status: str) -> bool:
        """Update message status by client message ID."""
        try:
            result = await db.execute(
                select(MessageHistory).where(MessageHistory.message_id_client == message_id_client)
            )
            message = result.scalar_one_or_none()

            if message:
                message.status = status
                message.updated_at = datetime.now(timezone.utc)
                await db.commit()
                return True
            return False
        except Exception:
            await db.rollback()
            return False


# Create instance
message_crud = CRUDMessage(MessageHistory)
