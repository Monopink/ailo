"""
LeanMessage System Conversation Manager for Bots Service
Handles creation and management of LeanMessage system conversations for bots
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..core.config import settings
import structlog

logger = structlog.get_logger(__name__)


class LeanMessageManager:
    """LeanMessage system conversation management"""

    def __init__(self):
        self.app_id = settings.LEANCLOUD_APP_ID
        self.app_key = settings.LEANCLOUD_APP_KEY
        self.master_key = settings.LEANCLOUD_MASTER_KEY
        self.base_url = settings.LEANCLOUD_BASE_URL

        if not all([self.app_id, self.app_key, self.master_key, self.base_url]):
            raise ValueError("Missing required LeanMessage configuration")

    def _get_headers(self, use_master_key: bool = True) -> Dict[str, str]:
        """Get request headers"""
        if use_master_key:
            key = f"{self.master_key},master"
        else:
            key = self.app_key

        return {"X-LC-Id": self.app_id, "X-LC-Key": key, "Content-Type": "application/json"}

    async def create_system_conversation(
        self, name: str, description: str = "AI Chat Bot"
    ) -> Optional[Dict[str, Any]]:
        """
        Create system conversation (service account)

        Args:
            name: Conversation name (should be entity_id)
            description: Conversation description

        Returns:
            Conversation info if successful, None if failed
        """
        url = f"{self.base_url}/1.2/rtm/service-conversations"

        headers = self._get_headers(use_master_key=True)

        data = {
            "name": name,
            "sys": True,  # Mark as system conversation
            "attr": {
                "description": description,
                "created_by": "says_bots_service",
                "created_at": datetime.now().isoformat(),
            },
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            logger.info(
                "system_conversation_created",
                conversation_id=result.get("objectId"),
                name=name,
                description=description,
            )

            return result

        except requests.exceptions.RequestException as e:
            logger.error(
                "create_system_conversation_failed",
                error=str(e),
                name=name,
                response_text=getattr(e.response, "text", None) if hasattr(e, "response") else None,
            )
            return None

    async def list_conversations(self) -> Optional[List[Dict[str, Any]]]:
        """
        List existing conversations

        Returns:
            List of conversations, None if failed
        """
        url = f"{self.base_url}/1.1/classes/_Conversation"

        headers = self._get_headers(use_master_key=True)

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            result = response.json()
            conversations = result.get("results", [])

            logger.info("conversations_listed", count=len(conversations))

            # Categorize conversations
            system_convs = [c for c in conversations if c.get("sys", False)]
            normal_convs = [c for c in conversations if not c.get("sys", False)]

            logger.info(
                "conversation_summary",
                total=len(conversations),
                system_conversations=len(system_convs),
                normal_conversations=len(normal_convs),
            )

            return conversations

        except requests.exceptions.RequestException as e:
            logger.error("list_conversations_failed", error=str(e))
            return None

    async def setup_bot_system_conversations(self) -> Dict[str, Any]:
        """
        Create system conversations for all bots and update bot records

        Returns:
            Creation result statistics
        """
        from ..database import AsyncSessionLocal
        from ..models.bot import Bot
        from sqlalchemy import select

        try:
            # Get all bots from database
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Bot))
                bots = result.scalars().all()

            results = {"total_bots": len(bots), "created": [], "failed": [], "existing": [], "updated": []}

            # Get existing conversations
            existing_conversations = await self.list_conversations()
            existing_names = {conv.get("name") for conv in existing_conversations or []}

            for bot in bots:
                entity_id = bot.entity_id

                # Check if bot already has a conversation ID
                if bot.leancloud_conversation_id:
                    logger.info(
                        "bot_already_has_conversation_id",
                        entity_id=entity_id,
                        conversation_id=bot.leancloud_conversation_id,
                    )
                    results["existing"].append(
                        {"entity_id": entity_id, "conversation_id": bot.leancloud_conversation_id}
                    )
                    continue

                # Check if conversation with this name already exists
                if entity_id in existing_names:
                    logger.info("system_conversation_name_exists", entity_id=entity_id)
                    # Find the conversation ID and update bot record
                    for conv in existing_conversations or []:
                        if conv.get("name") == entity_id:
                            conversation_id = conv.get("objectId")
                            if conversation_id:
                                await self._update_bot_conversation_id(bot.id, conversation_id)
                                results["updated"].append(
                                    {"entity_id": entity_id, "conversation_id": conversation_id}
                                )
                            break
                    continue

                # Create new system conversation
                description = f"AI Chat Bot - {entity_id}"
                result = await self.create_system_conversation(entity_id, description)

                if result:
                    conversation_id = result.get("objectId")
                    if conversation_id:
                        # Update bot record with conversation ID
                        await self._update_bot_conversation_id(bot.id, conversation_id)

                        results["created"].append(
                            {"entity_id": entity_id, "conversation_id": conversation_id}
                        )
                        logger.info(
                            "bot_conversation_created_and_updated",
                            entity_id=entity_id,
                            conversation_id=conversation_id,
                        )
                else:
                    results["failed"].append(entity_id)

            logger.info("bot_system_conversations_setup_complete", results=results)
            return results

        except Exception as e:
            logger.error("setup_bot_system_conversations_failed", error=str(e))
            return {"error": str(e)}

    async def _update_bot_conversation_id(self, bot_id: int, conversation_id: str) -> bool:
        """Update bot's LeanMessage conversation ID"""
        from ..database import AsyncSessionLocal
        from ..models.bot import Bot
        from sqlalchemy import select

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Bot).where(Bot.id == bot_id))
                bot = result.scalar_one_or_none()

                if bot:
                    bot.leancloud_conversation_id = conversation_id
                    await session.commit()
                    logger.info(
                        "bot_conversation_id_updated", bot_id=bot_id, conversation_id=conversation_id
                    )
                    return True
                else:
                    logger.warning("bot_not_found_for_conversation_update", bot_id=bot_id)
                    return False

        except Exception as e:
            logger.error("update_bot_conversation_id_failed", bot_id=bot_id, error=str(e))
            return False


# Create global instance
leanmessage_manager = LeanMessageManager()
