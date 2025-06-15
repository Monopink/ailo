import logging
from db_managers import db_manager
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def load_emotions(self) -> None:
    """Load current emotion data from the database into the in-memory state."""
    try:
        self.emotions = await db_manager.get_emotions_data(self.bot.id)
    except Exception as e:
        logger.error(f"Error loading emotions for bot {self.bot.id}: {str(e)}")
        self.emotions = {}


async def save_bot_state(self) -> None:
    """
    Persists all modified in-memory bot state to the database.
    This includes core bot attributes, context, memory in one call,
    and emotions data in a separate call.
    """
    try:
        # 1. Prepare bot data update payload
        update_payload: Dict[str, Any] = {}

        # Compare in-memory state with the initial state from self.bot to build the payload
        update_payload["friend_score"] = self.friend_score
        update_payload["friend_score_cap"] = self.friend_score_cap
        update_payload["friend_score_floor"] = self.friend_score_floor
        update_payload["friend_score_peak"] = self.friend_score_peak
        update_payload["friend_score_trough"] = self.friend_score_trough
        update_payload["romance_score"] = self.romance_score
        update_payload["romance_score_cap"] = self.romance_score_cap
        update_payload["romance_score_peak"] = self.romance_score_peak
        update_payload["relationship_type"] = self.relationship_type
        update_payload["relationship_level"] = self.relationship_level
        update_payload["friend_level"] = self.friend_level
        update_payload["romance_level"] = self.romance_level
        update_payload["friend_buffer_status"] = self.friend_buffer_status
        update_payload["romance_buffer_status"] = self.romance_buffer_status
        update_payload["relationship_style"] = self.relationship_style
        update_payload["is_polite"] = self.is_polite
        update_payload["is_crushing"] = self.is_crushing
        update_payload["last_chat_time"] = self.last_chat_time
        update_payload["context"] = self.context
        update_payload["memory"] = self.memory
        update_payload["context_metadata"] = self.context_metadata

        # 2. Update bot data if needed
        if update_payload:
            logger.info(f"Saving bot data for bot {self.bot.id}. Fields: {list(update_payload.keys())}")
            await db_manager.update_bot_data(
                bot_id=self.bot.id,
                bot_data=update_payload,
            )
            logger.debug(f"Successfully saved bot data for bot {self.bot.id}")

        # 3. Update emotions data separately if needed
        if self.emotions:
            logger.info(f"Saving emotions data for bot {self.bot.id}")
            await db_manager.update_emotions_data(bot_id=self.bot.id, emotions=self.emotions)
            logger.debug(f"Successfully saved emotions data for bot {self.bot.id}")

        if not update_payload and not self.emotions:
            logger.debug(f"No state changes to save for bot {self.bot.id}")

    except Exception as e:
        logger.error(f"Error saving bot state for bot {self.bot.id}: {str(e)}", exc_info=True)
        raise
