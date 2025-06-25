import copy
from ..db_managers import db_manager
from typing import Dict, Any


async def load_emotions(self) -> None:
    """Load current emotion data from the database into the in-memory state."""
    try:
        self.emotions = await db_manager.get_emotions_data(self.bot.id)
        self.logger.info("emotions_loaded", emotions=self.emotions)
        self.loaded_emotions = True
    except Exception as e:
        self.logger.error("error_loading_emotions", error=str(e))
        self.emotions = {}


async def save_bot_state(self) -> None:
    """
    Persists all modified in-memory bot state to the database.
    This includes core bot attributes, context, memory in one call,
    and emotions data in a separate call.
    The system message from the context is excluded from persistence
    as it's dynamically regenerated each session.
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

        # Handle context persistence: exclude the system message
        context_to_save = copy.deepcopy(self.context)
        if (
            context_to_save
            and "messages" in context_to_save
            and isinstance(context_to_save["messages"], list)
            and context_to_save["messages"]
            and context_to_save["messages"][0].get("role") == "system"
        ):
            # Clear the content of the system prompt instead of removing the object
            context_to_save["messages"][0]["content"] = ""
            self.logger.info("Cleared system prompt content before saving to DB.")

        update_payload["context"] = context_to_save
        update_payload["memory"] = self.memory
        update_payload["context_metadata"] = self.context_metadata

        # 2. Update bot data if needed
        if update_payload:
            self.logger.info("saving_bot_data", fields=list(update_payload.keys()))
            await db_manager.update_bot_data(bot_id=self.bot.id, bot_data=update_payload)
            self.logger.info("bot_data_saved")

        # 3. Update emotions data separately if needed
        if self.emotions:
            self.logger.info("saving_emotions_data")
            await db_manager.update_emotions_data(bot_id=self.bot.id, emotions=self.emotions)
            self.logger.info("emotions_data_saved")

        if not update_payload and not self.emotions:
            self.logger.info("no_state_changes")

    except Exception as e:
        self.logger.error("error_saving_bot_state", error=str(e), exc_info=True)
        raise
