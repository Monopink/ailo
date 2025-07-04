"""
CRUD operations for Bot and related entities.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, update
from .base_crud import CRUDBase
from ..models.bot import Bot
from ..models.emotion import Emotions


class CRUDBot(CRUDBase[Bot]):
    """CRUD operations for Bot and related emotion data."""

    async def get_by_entity_id(self, db: AsyncSession, entity_id: str) -> Optional[Bot]:
        """Get bot by entity_id."""
        result = await db.execute(select(Bot).where(Bot.entity_id == entity_id))
        return result.scalar_one_or_none()

    async def get_bot_data(self, db: AsyncSession, bot_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get bot data with optional user filtering."""
        query = select(Bot).where(Bot.id == bot_id)
        if user_id is not None:
            query = query.where(Bot.user_id == user_id)
        
        result = await db.execute(query)
        bot = result.scalar_one_or_none()
        
        if not bot:
            return None
            
        # Convert to dict (you may want to customize this based on your needs)
        return {
            "id": bot.id,
            "entity_id": bot.entity_id,
            "model": bot.model,
            "status": bot.status,
            "gender": bot.gender,
            "friend_score": bot.friend_score,
            "romance_score": bot.romance_score,
            "relationship_type": bot.relationship_type,
            "relationship_level": bot.relationship_level,
            "friend_level": bot.friend_level,
            "romance_level": bot.romance_level,
            "context": bot.context,
            "context_metadata": bot.context_metadata,
            "info": bot.info,
            "memory": bot.memory,
            # Add other fields as needed
        }

    async def update_bot_data(self, db: AsyncSession, bot_id: int, data: Dict[str, Any]) -> bool:
        """Update bot data."""
        try:
            # Build update statement
            stmt = update(Bot).where(Bot.id == bot_id).values(**data)
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount > 0
        except Exception:
            await db.rollback()
            return False

    # Emotion-related operations (strongly coupled with Bot)
    async def get_bot_emotions(self, db: AsyncSession, bot_id: int) -> Dict[str, Any]:
        """Get all emotions for a bot."""
        result = await db.execute(
            select(Emotions).where(Emotions.bot_id == bot_id, Emotions.is_ended == 0)
        )
        emotions = result.scalars().all()
        
        # Convert to dict format expected by the application
        emotions_dict = {}
        for emotion in emotions:
            emotions_dict[emotion.emotion_type] = {
                "emotion_score": emotion.emotion_score,
                "original_emotion_score": emotion.original_emotion_score,
                "emotion_level": emotion.emotion_level,
                "friend_score_delta": emotion.friend_score_delta,
                "original_friend_score_delta": emotion.original_friend_score_delta,
                "romance_score_delta": emotion.romance_score_delta,
                "original_romance_score_delta": emotion.original_romance_score_delta,
                "decay_ratio": float(emotion.decay_ratio) if emotion.decay_ratio else 0.8,
                "start_time": emotion.start_time,
                "end_time": emotion.end_time,
                "original_end_time": emotion.original_end_time,
                "is_ended": emotion.is_ended,
                "update_time": emotion.update_time,
            }
        
        return emotions_dict

    async def update_bot_emotions(self, db: AsyncSession, bot_id: int, emotions: Dict[str, Any]) -> bool:
        """Update emotions for a bot."""
        try:
            # This is a complex operation that might involve:
            # 1. Updating existing emotions
            # 2. Creating new emotions
            # 3. Ending old emotions
            
            # For now, implement a simple version
            # You may need to customize this based on your specific requirements
            
            for emotion_type, emotion_data in emotions.items():
                # Check if emotion already exists
                result = await db.execute(
                    select(Emotions).where(
                        Emotions.bot_id == bot_id,
                        Emotions.emotion_type == emotion_type,
                        Emotions.is_ended == 0
                    )
                )
                existing_emotion = result.scalar_one_or_none()
                
                if existing_emotion:
                    # Update existing emotion
                    for key, value in emotion_data.items():
                        if hasattr(existing_emotion, key):
                            setattr(existing_emotion, key, value)
                else:
                    # Create new emotion
                    new_emotion = Emotions(
                        bot_id=bot_id,
                        emotion_type=emotion_type,
                        **emotion_data
                    )
                    db.add(new_emotion)
            
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False

    # LeanCloud conversation mapping operations (related to Bot)
    async def get_bot_by_conversation_id(self, db: AsyncSession, conversation_id: str) -> Optional[str]:
        """Get bot entity_id from LeanCloud conversation ID."""
        result = await db.execute(
            text("SELECT contact_entity_id FROM conversation_mappings WHERE conversation_id = :conv_id AND im_service_type = 'leancloud'"),
            {"conv_id": conversation_id}
        )
        row = result.fetchone()
        return row[0] if row else None

    async def get_conversation_id_by_bot(self, db: AsyncSession, bot_entity_id: str) -> Optional[str]:
        """Get LeanCloud conversation ID from bot entity_id."""
        result = await db.execute(
            text("SELECT conversation_id FROM conversation_mappings WHERE contact_entity_id = :bot_id AND im_service_type = 'leancloud'"),
            {"bot_id": bot_entity_id}
        )
        row = result.fetchone()
        return row[0] if row else None


# Create instance
bot_crud = CRUDBot(Bot)
