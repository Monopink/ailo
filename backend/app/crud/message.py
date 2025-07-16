"""
CRUD operations for Message processing.
"""

from typing import Dict, Any, List, Union
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from .base_crud import CRUDBase
from ..models.message import MessageHistory
from ...utils.logging import get_logger, bind_context

logger = get_logger(__name__)


class CRUDMessage(CRUDBase[MessageHistory]):
    """CRUD operations for message processing."""

    def _parse_message_time(self, message_time: Union[str, datetime, None]) -> datetime:
        """Parse message_time from various formats to datetime object."""
        if message_time is None:
            return datetime.now(timezone.utc)

        if isinstance(message_time, datetime):
            return message_time

        if isinstance(message_time, str):
            try:
                # Handle ISO format with 'Z' suffix
                if message_time.endswith("Z"):
                    message_time = message_time[:-1] + "+00:00"

                # Parse ISO format
                return datetime.fromisoformat(message_time)
            except ValueError:
                # If parsing fails, return current time
                return datetime.now(timezone.utc)

        return datetime.now(timezone.utc)

    async def save_message(self, db: AsyncSession, message: Dict[str, Any]) -> MessageHistory:
        """Save a message to the database with strict validation."""
        # Create contextualized logger for this operation
        op_logger = bind_context(
            logger, operation="save_message", message_id_client=message.get("message_id_client")
        )

        # Strict validation - check required fields
        validation_errors = []
        required_fields = ["from_entity", "to_entity", "content", "message_service"]

        for field in required_fields:
            if not message.get(field):
                validation_errors.append(f"Missing or empty required field: {field}")

        # Log validation errors but continue to save data for completeness
        if validation_errors:
            op_logger.error(
                "message_validation_failed",
                errors=validation_errors,
                message_data=message,
                action="attempting_to_save_anyway_for_data_integrity",
            )

        # Additional field validation with detailed logging
        message_id_client = message.get("message_id_client")
        if not message_id_client:
            op_logger.warning("missing_message_id_client", message_data=message)

        from_entity = message.get("from_entity")
        if not from_entity:
            op_logger.error("missing_from_entity", message_data=message)

        to_entity = message.get("to_entity")
        if not to_entity:
            op_logger.error("missing_to_entity", message_data=message)

        content = message.get("content")
        if not content:
            op_logger.error("missing_content", message_data=message)

        message_service = message.get("message_service")
        if not message_service:
            op_logger.error("missing_message_service", message_data=message)

        # Check for potentially problematic values
        message_type = message.get("message_type")
        if not message_type:
            op_logger.warning("missing_message_type", message_data=message, default_used="chat")

        status = message.get("status")
        if not status:
            op_logger.warning("missing_status", message_data=message, default_used="sent")

        try:
            # Create message record - still save even with validation errors for data integrity
            message_record = MessageHistory(
                message_id=message.get("message_id"),  # Backend-generated message ID
                message_id_client=message_id_client,
                from_entity=from_entity,
                to_entity=to_entity,
                content=content,
                message_type=message_type or "chat",  # Use default only if None/empty
                message_service=message_service,
                message_time=self._parse_message_time(message.get("message_time")),
                status=status or "sent",  # Use default only if None/empty
                message_metadata=message.get("message_metadata"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            db.add(message_record)
            await db.commit()
            await db.refresh(message_record)

            if validation_errors:
                op_logger.info(
                    "message_saved_despite_validation_errors",
                    message_id=message_record.id,
                    errors=validation_errors,
                )
            else:
                op_logger.info("message_saved_successfully", message_id=message_record.id)

            return message_record

        except Exception as e:
            await db.rollback()
            op_logger.error(
                "message_save_failed",
                error=str(e),
                message_data=message,
                validation_errors=validation_errors,
            )
            raise

    async def get_messages_by_entities(
        self, db: AsyncSession, from_entity: str, to_entity: str, limit: int = 10
    ) -> List[MessageHistory]:
        """Get messages between two entities."""
        result = await db.execute(
            select(MessageHistory)
            .where(
                or_(
                    and_(MessageHistory.from_entity == from_entity, MessageHistory.to_entity == to_entity),
                    and_(MessageHistory.from_entity == to_entity, MessageHistory.to_entity == from_entity),
                )
            )
            .order_by(desc(MessageHistory.message_time))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_messages_by_bot(
        self, db: AsyncSession, from_entity: str, to_entity: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get session history messages."""
        query = (
            select(MessageHistory)
            .where(
                or_(
                    and_(MessageHistory.from_entity == from_entity, MessageHistory.to_entity == to_entity),
                    and_(MessageHistory.from_entity == to_entity, MessageHistory.to_entity == from_entity),
                )
            )
            .order_by(desc(MessageHistory.created_at))
            .limit(limit)
        )

        result = await db.execute(query)
        messages = result.scalars().all()
        return [self._message_to_dict(msg) for msg in messages]

    def _message_to_dict(self, message: MessageHistory) -> Dict[str, Any]:
        """Convert MessageHistory object to dictionary."""
        return {
            "id": message.id,
            "message_id_client": message.message_id_client,
            "from_entity": message.from_entity,
            "to_entity": message.to_entity,
            "content": message.content,
            "message_type": message.message_type,
            "message_service": message.message_service,
            "message_time": message.message_time.isoformat() if message.message_time else None,
            "status": message.status,
            "message_metadata": message.message_metadata,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        }

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
