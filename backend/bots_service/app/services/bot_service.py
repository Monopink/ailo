"""
Bot Service - Business logic for bot operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select
from ..database import AsyncSessionLocal
from ..models.bot import Bot
import structlog

logger = structlog.get_logger(__name__)


class BotService:
    """Service class for bot-related operations"""

    async def get_user_bots(self, user_entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all bots for a specific user
        
        Args:
            user_entity_id: User's entity ID
            
        Returns:
            List of bot dictionaries
        """
        try:
            async with AsyncSessionLocal() as session:
                # Filter bots by user_entity_id
                result = await session.execute(select(Bot).where(Bot.user_entity_id == user_entity_id))
                bots = result.scalars().all()

                bot_list = []
                for bot in bots:
                    bot_list.append({
                        "id": bot.id,
                        "entity_id": bot.entity_id,
                        "nickname": bot.nickname or bot.entity_id,
                        "bio": bot.bio or f"我是{bot.nickname or bot.entity_id}，很高兴认识你！",
                        "gender": bot.gender,
                        "relationship_type": bot.relationship_type,
                        "relationship_level": bot.relationship_level,
                        "friend_score": bot.friend_score,
                        "romance_score": bot.romance_score,
                        "leancloud_conversation_id": bot.leancloud_conversation_id,
                        "avatar_url": bot.avatar_url,
                        "status": bot.status,
                    })

                logger.info("user_bots_retrieved", user_entity_id=user_entity_id, count=len(bot_list))
                return bot_list

        except Exception as e:
            logger.error("get_user_bots_error", error=str(e), user_entity_id=user_entity_id)
            raise

    async def get_bot_by_id(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific bot by ID
        
        Args:
            bot_id: Bot's database ID
            
        Returns:
            Bot dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()

                if not bot:
                    return None

                return {
                    "id": bot.id,
                    "entity_id": bot.entity_id,
                    "nickname": bot.nickname or bot.entity_id,
                    "bio": bot.bio or f"我是{bot.nickname or bot.entity_id}，很高兴认识你！",
                    "gender": bot.gender,
                    "relationship_type": bot.relationship_type,
                    "relationship_level": bot.relationship_level,
                    "friend_score": bot.friend_score,
                    "romance_score": bot.romance_score,
                    "leancloud_conversation_id": bot.leancloud_conversation_id,
                    "avatar_url": bot.avatar_url,
                    "status": bot.status,
                }

        except Exception as e:
            logger.error("get_bot_by_id_error", error=str(e), bot_id=bot_id)
            raise

    async def get_bot_by_entity_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific bot by entity ID
        
        Args:
            entity_id: Bot's entity ID
            
        Returns:
            Bot dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Bot).where(Bot.entity_id == entity_id))
                bot = result.scalar_one_or_none()

                if not bot:
                    return None

                return {
                    "id": bot.id,
                    "entity_id": bot.entity_id,
                    "nickname": bot.nickname or bot.entity_id,
                    "bio": bot.bio or f"我是{bot.nickname or bot.entity_id}，很高兴认识你！",
                    "gender": bot.gender,
                    "relationship_type": bot.relationship_type,
                    "relationship_level": bot.relationship_level,
                    "friend_score": bot.friend_score,
                    "romance_score": bot.romance_score,
                    "leancloud_conversation_id": bot.leancloud_conversation_id,
                    "avatar_url": bot.avatar_url,
                    "status": bot.status,
                }

        except Exception as e:
            logger.error("get_bot_by_entity_id_error", error=str(e), entity_id=entity_id)
            raise


# Create global instance
bot_service = BotService()
