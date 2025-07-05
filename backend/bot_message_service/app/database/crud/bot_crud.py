"""
CRUD operations for Bot and related entities.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from .base_crud import CRUDBase
from ..models.bot import Bot
from ...enums import BotStatus, IMServiceType
from ...utils.logging import get_logger, bind_context
import enum

logger = get_logger(__name__)


class CRUDBot(CRUDBase[Bot]):
    """CRUD operations for Bot and related emotion data."""

    def _convert_enum_to_str(self, value: Optional[enum.Enum]) -> Optional[str]:
        """Convert enum value to string."""
        return value.value.lower() if value is not None else None

    def _convert_emotions_config_keys(self, config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Converts string keys in emotions_config thresholds to integers for safety."""
        if not config or not isinstance(config, dict):
            return config

        try:
            new_config = {}
            for emotion_type, details in config.items():
                if (
                    isinstance(details, dict)
                    and "thresholds" in details
                    and isinstance(details.get("thresholds"), dict)
                ):
                    # Create a copy of details to avoid modifying the original dict in-place
                    new_details = details.copy()
                    new_details["thresholds"] = {int(k): v for k, v in details["thresholds"].items()}
                    new_config[emotion_type] = new_details
                else:
                    new_config[emotion_type] = details
            return new_config
        except (ValueError, TypeError) as e:
            logger.warning("failed_to_convert_emotions_config_keys", config=config, error=str(e))
            return config  # Return original on error

    def _convert_str_to_enum(self, enum_class: type, value: Optional[str]) -> Optional[enum.Enum]:
        """Convert string to enum value."""
        if value is None:
            return None
        try:
            return enum_class.__members__[value.upper()]
        except KeyError:
            logger.warning("invalid_enum_value", value=value, enum_class=enum_class.__name__)
            return None

    async def get_by_entity_id(self, db: AsyncSession, entity_id: str) -> Optional[Bot]:
        """Get bot by entity_id."""
        try:
            # Create contextualized logger for this operation
            op_logger = bind_context(logger, operation="get_bot_by_entity_id", entity_id=entity_id)
            op_logger.info("fetching_bot_by_entity_id")

            result = await db.execute(select(Bot).where(Bot.entity_id == entity_id))
            bot = result.scalar_one_or_none()

            if bot:
                # Convert enum value
                bot.status = self._convert_str_to_enum(BotStatus, bot.status)
                # Convert emotions_config keys
                if bot.emotions_config:
                    bot.emotions_config = self._convert_emotions_config_keys(bot.emotions_config)
                op_logger.info("bot_found", status=str(bot.status))
            else:
                op_logger.info("bot_not_found")

            return bot
        except SQLAlchemyError as e:
            logger.error("database_error_get_bot_by_entity_id", entity_id=entity_id, error=str(e))
            raise Exception(f"Failed to get bot by entity_id: {str(e)}") from e

    async def get_bot_data(
        self, db: AsyncSession, bot_id: int, related_user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get all relevant data for a bot."""
        try:
            result = await db.execute(select(Bot).where(Bot.id == bot_id))
            bot = result.scalar_one_or_none()

            if bot and (bot.user_id is None or bot.user_id == related_user_id):
                # Build relationship dictionary
                relationship = {
                    "type": bot.relationship_type,
                    "level": bot.relationship_level,
                    "style": bot.relationship_style,
                }

                return {
                    "context": bot.context,
                    "info": bot.info,
                    "memory": bot.memory,
                    "friend_score": bot.friend_score,
                    "romance_score": bot.romance_score,
                    "relationship": relationship,
                    "friend_config": bot.friend_config,
                    "romance_config": bot.romance_config,
                    "override_config": bot.override_config,
                    "is_polite": bool(bot.is_polite),
                    "is_crushing": bool(bot.is_crushing),
                    "emotions_config": self._convert_emotions_config_keys(bot.emotions_config),
                }
            return None
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_bot_data: {str(e)}")
            raise Exception(f"Failed to get bot data: {str(e)}") from e

    async def update_bot_data(self, db: AsyncSession, bot_id: int, bot_data: Dict[str, Any]) -> None:
        """Update bot information based on a dictionary of changes with strict validation."""
        # Create contextualized logger for this operation
        op_logger = bind_context(logger, operation="update_bot_data", bot_id=bot_id)

        # Strict validation - check if bot_id is valid
        if not bot_id or not isinstance(bot_id, int) or bot_id <= 0:
            op_logger.error("invalid_bot_id", bot_id=bot_id, bot_data=bot_data)
            raise ValueError(f"Invalid bot_id: {bot_id}")

        # Validate bot_data is not empty
        if not bot_data:
            op_logger.error("empty_bot_data", bot_id=bot_id)
            raise ValueError("bot_data cannot be empty")

        # Log all fields being updated for audit trail
        op_logger.info("updating_bot_fields", fields=list(bot_data.keys()), values_count=len(bot_data))

        # Check for potentially problematic values and log them
        validation_warnings = []
        for key, value in bot_data.items():
            if value is None:
                validation_warnings.append(f"Field '{key}' is being set to None")
            elif isinstance(value, str) and not value.strip():
                validation_warnings.append(f"Field '{key}' is being set to empty string")

        if validation_warnings:
            op_logger.warning(
                "bot_data_validation_warnings",
                warnings=validation_warnings,
                bot_data=bot_data,
                action="proceeding_with_update_for_data_integrity",
            )

        try:
            stmt = select(Bot).where(Bot.id == bot_id)
            result = await db.execute(stmt)
            bot = result.scalar_one_or_none()

            if not bot:
                op_logger.error("bot_not_found", bot_id=bot_id, attempted_update=bot_data)
                raise ValueError(f"Bot not found with id: {bot_id}")

            # Track which fields actually exist on the model
            valid_fields = []
            invalid_fields = []

            for key, value in bot_data.items():
                if hasattr(bot, key):
                    old_value = getattr(bot, key)
                    setattr(bot, key, value)
                    valid_fields.append(key)

                    # Log significant changes
                    if old_value != value:
                        op_logger.info("field_updated", field=key, old_value=old_value, new_value=value)
                else:
                    invalid_fields.append(key)
                    op_logger.error(
                        "invalid_field_attempted", field=key, value=value, action="field_ignored"
                    )

            if invalid_fields:
                op_logger.warning(
                    "some_fields_ignored", invalid_fields=invalid_fields, valid_fields=valid_fields
                )

            await db.commit()

            op_logger.info(
                "bot_update_completed",
                updated_fields=valid_fields,
                ignored_fields=invalid_fields,
                validation_warnings=validation_warnings,
            )

        except ValueError:
            # Re-raise ValueError as is (bot not found, invalid bot_id, etc.)
            raise
        except Exception as e:
            await db.rollback()
            op_logger.error(
                "bot_update_failed",
                error=str(e),
                bot_id=bot_id,
                bot_data=bot_data,
                validation_warnings=validation_warnings,
            )
            raise

    # Emotion-related operations (strongly coupled with Bot)
    async def get_bot_emotions(self, db: AsyncSession, bot_id: int) -> Dict[str, Dict[str, Any]]:
        """Get the current active emotions for a bot

        Retrieves emotions that have not ended (is_ended=FALSE).
        If there are multiple active emotions of the same type, selects the one with the most recent start_time.

        Args:
            bot_id: Bot ID

        Returns:
            Dict[str, Dict[str, Any]]: Mapping from emotion type to emotion details
        """
        try:
            now = datetime.now(timezone.utc)

            # Query for valid emotions that have not ended
            query = """
            SELECT e.*
            FROM emotions e
            INNER JOIN (
                SELECT emotion_type, MAX(start_time) as latest_start_time
                FROM emotions
                WHERE bot_id = :bot_id
                    AND start_time IS NOT NULL
                    AND is_ended = FALSE
                GROUP BY emotion_type
            ) latest ON e.emotion_type = latest.emotion_type AND e.start_time = latest.latest_start_time
            WHERE e.bot_id = :bot_id
            """

            result = await db.execute(text(query), {"bot_id": bot_id, "now": now})
            emotions = result.fetchall()

            # Check for duplicate emotions with the same type and start_time
            emotion_counts = {}
            for emotion in emotions:
                emotion_type = emotion.emotion_type
                if emotion_type in emotion_counts:
                    emotion_counts[emotion_type] += 1
                else:
                    emotion_counts[emotion_type] = 1

            # Log warning for duplicate emotions
            for emotion_type, count in emotion_counts.items():
                if count > 1:
                    logger.warning(
                        f"Multiple active emotions found for bot {bot_id}, type {emotion_type}. "
                        f"Using the one with most recent start_time."
                    )

            # Build the return result
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
                    "decay_ratio": (float(emotion.decay_ratio) if emotion.decay_ratio else 0.8),
                    "start_time": (emotion.start_time.isoformat() if emotion.start_time else None),
                    "end_time": (emotion.end_time.isoformat() if emotion.end_time else None),
                    "original_end_time": (
                        emotion.original_end_time.isoformat() if emotion.original_end_time else None
                    ),
                    "is_ended": bool(emotion.is_ended),
                    "update_time": (emotion.update_time.isoformat() if emotion.update_time else None),
                }

            return emotions_dict

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_current_bot_emotions: {str(e)}")
            raise Exception(f"Failed to get current bot emotions: {str(e)}") from e

    async def update_bot_emotions(
        self, db: AsyncSession, bot_id: int, emotions: Dict[str, Dict[str, Any]]
    ) -> bool:
        """Batch update a bot's emotion data with strict validation

        If there exists an emotion with the same emotion_type and same start_time,
        update that emotion, otherwise create a new emotion record.

        Args:
            bot_id: Bot ID
            emotions: Emotion data in format {emotion_type: {emotion_details}}

        Returns:
            bool: Whether the update was successful
        """
        # Create contextualized logger for this operation
        op_logger = bind_context(logger, operation="update_emotions_data", bot_id=bot_id)

        # Strict validation - check if bot_id is valid
        if not bot_id or not isinstance(bot_id, int) or bot_id <= 0:
            op_logger.error("invalid_bot_id", bot_id=bot_id, emotions_data=emotions)
            raise ValueError(f"Invalid bot_id: {bot_id}")

        # Validate emotions data is not empty
        if not emotions:
            op_logger.error("empty_emotions_data", bot_id=bot_id)
            raise ValueError("emotions data cannot be empty")

        # Validate emotions structure
        validation_errors = []
        for emotion_type, emotion_data in emotions.items():
            if not emotion_type or not isinstance(emotion_type, str):
                validation_errors.append(f"Invalid emotion_type: {emotion_type}")

            if not isinstance(emotion_data, dict):
                validation_errors.append(f"emotion_data for {emotion_type} must be a dictionary")
                continue

            # Check for required fields in emotion_data
            if not emotion_data:
                validation_errors.append(f"Empty emotion_data for {emotion_type}")

        # Log validation errors but continue for data integrity
        if validation_errors:
            op_logger.error(
                "emotions_validation_failed",
                errors=validation_errors,
                bot_id=bot_id,
                emotions_data=emotions,
                action="attempting_to_save_anyway_for_data_integrity",
            )

        op_logger.info(
            "updating_emotions", emotion_count=len(emotions), validation_errors=validation_errors
        )

        try:

            for emotion_type, emotion_data in emotions.items():
                # Skip invalid emotion types (already logged in validation)
                if not emotion_type or not isinstance(emotion_type, str):
                    op_logger.warning("skipping_invalid_emotion_type", emotion_type=emotion_type)
                    continue

                if not isinstance(emotion_data, dict):
                    op_logger.warning("skipping_invalid_emotion_data", emotion_type=emotion_type)
                    continue

                # Parse time fields with strict validation
                start_time = None
                if "start_time" in emotion_data and emotion_data["start_time"]:
                    try:
                        if isinstance(emotion_data["start_time"], str):
                            start_time = datetime.fromisoformat(
                                emotion_data["start_time"].replace("Z", "+00:00")
                            )
                        else:
                            start_time = emotion_data["start_time"]
                    except (ValueError, TypeError) as e:
                        op_logger.error(
                            "invalid_start_time_format",
                            emotion_type=emotion_type,
                            start_time_value=emotion_data["start_time"],
                            error=str(e),
                            action="using_current_time_as_fallback",
                        )
                        start_time = datetime.now(timezone.utc)
                else:
                    op_logger.warning(
                        "missing_start_time",
                        emotion_type=emotion_type,
                        action="using_current_time_as_default",
                    )
                    start_time = datetime.now(timezone.utc)

                end_time = None
                if "end_time" in emotion_data and emotion_data["end_time"]:
                    try:
                        if isinstance(emotion_data["end_time"], str):
                            end_time = datetime.fromisoformat(
                                emotion_data["end_time"].replace("Z", "+00:00")
                            )
                        else:
                            end_time = emotion_data["end_time"]
                    except (ValueError, TypeError) as e:
                        op_logger.error(
                            "invalid_end_time_format",
                            emotion_type=emotion_type,
                            end_time_value=emotion_data["end_time"],
                            error=str(e),
                            action="using_start_time_plus_one_hour_as_fallback",
                        )
                        end_time = start_time + timedelta(hours=1)
                else:
                    op_logger.warning(
                        "missing_end_time",
                        emotion_type=emotion_type,
                        action="using_start_time_plus_one_hour_as_default",
                    )
                    # Default end time is start time plus one hour
                    end_time = start_time + timedelta(hours=1)

                original_end_time = None
                if "original_end_time" in emotion_data and emotion_data["original_end_time"]:
                    try:
                        if isinstance(emotion_data["original_end_time"], str):
                            original_end_time = datetime.fromisoformat(
                                emotion_data["original_end_time"].replace("Z", "+00:00")
                            )
                        else:
                            original_end_time = emotion_data["original_end_time"]
                    except (ValueError, TypeError) as e:
                        op_logger.error(
                            "invalid_original_end_time_format",
                            emotion_type=emotion_type,
                            original_end_time_value=emotion_data["original_end_time"],
                            error=str(e),
                            action="using_end_time_as_fallback",
                        )
                        original_end_time = end_time
                else:
                    op_logger.warning(
                        "missing_original_end_time",
                        emotion_type=emotion_type,
                        action="using_end_time_as_default",
                    )
                    # Default original end time is same as end time
                    original_end_time = end_time

                update_time = None
                if "update_time" in emotion_data and emotion_data["update_time"]:
                    if isinstance(emotion_data["update_time"], str):
                        update_time = datetime.fromisoformat(
                            emotion_data["update_time"].replace("Z", "+00:00")
                        )
                    else:
                        update_time = emotion_data["update_time"]
                else:
                    update_time = datetime.now(timezone.utc)

                # Get original values from data or use current values
                original_emotion_score = emotion_data.get(
                    "original_emotion_score", emotion_data.get("emotion_score", 0)
                )

                original_friend_score_delta = emotion_data.get(
                    "original_friend_score_delta",
                    emotion_data.get("friend_score_delta", 0),
                )

                original_romance_score_delta = emotion_data.get(
                    "original_romance_score_delta",
                    emotion_data.get("romance_score_delta", 0),
                )

                decay_ratio = emotion_data.get("decay_ratio", 0.8)
                is_ended = emotion_data.get("is_ended", False)

                # Find if there's an emotion with the same type and start time
                if start_time:
                    # Query for emotions with the same type and start time
                    query = """
                    SELECT * FROM emotions
                    WHERE bot_id = :bot_id
                    AND emotion_type = :emotion_type
                    AND start_time = :start_time
                    """

                    result = await db.execute(
                        text(query),
                        {
                            "bot_id": bot_id,
                            "emotion_type": emotion_type,
                            "start_time": start_time,
                        },
                    )
                    existing_emotion = result.fetchone()

                    if existing_emotion:
                        # Update existing emotion
                        update_query = """
                        UPDATE emotions
                        SET emotion_score = :emotion_score,
                            emotion_level = :emotion_level,
                            original_emotion_score = :original_emotion_score,
                            friend_score_delta = :friend_score_delta,
                            original_friend_score_delta = :original_friend_score_delta,
                            romance_score_delta = :romance_score_delta,
                            original_romance_score_delta = :original_romance_score_delta,
                            decay_ratio = :decay_ratio,
                            end_time = :end_time,
                            original_end_time = :original_end_time,
                            is_ended = :is_ended,
                            update_time = :update_time
                        WHERE id = :id
                        """

                        await db.execute(
                            text(update_query),
                            {
                                "id": existing_emotion.id,
                                "emotion_score": emotion_data.get(
                                    "emotion_score", existing_emotion.emotion_score
                                ),
                                "emotion_level": emotion_data.get(
                                    "emotion_level", existing_emotion.emotion_level
                                ),
                                "original_emotion_score": original_emotion_score,
                                "friend_score_delta": emotion_data.get("friend_score_delta", 0),
                                "original_friend_score_delta": original_friend_score_delta,
                                "romance_score_delta": emotion_data.get("romance_score_delta", 0),
                                "original_romance_score_delta": original_romance_score_delta,
                                "decay_ratio": decay_ratio,
                                "end_time": end_time,
                                "original_end_time": original_end_time,
                                "is_ended": is_ended,
                                "update_time": update_time,
                            },
                        )
                        op_logger.info(f"Updated existing emotion: {emotion_type} for bot {bot_id}")
                    else:
                        # Create new emotion
                        insert_query = """
                        INSERT INTO emotions
                        (bot_id, emotion_type, emotion_score, original_emotion_score, emotion_level,
                         friend_score_delta, original_friend_score_delta,
                         romance_score_delta, original_romance_score_delta,
                         decay_ratio, start_time, end_time, original_end_time, is_ended, update_time)
                        VALUES
                        (:bot_id, :emotion_type, :emotion_score, :original_emotion_score, :emotion_level,
                         :friend_score_delta, :original_friend_score_delta,
                         :romance_score_delta, :original_romance_score_delta,
                         :decay_ratio, :start_time, :end_time, :original_end_time, :is_ended, :update_time)
                        """

                        await db.execute(
                            text(insert_query),
                            {
                                "bot_id": bot_id,
                                "emotion_type": emotion_type,
                                "emotion_score": emotion_data.get("emotion_score", 0),
                                "original_emotion_score": original_emotion_score,
                                "emotion_level": emotion_data.get("emotion_level", 0),
                                "friend_score_delta": emotion_data.get("friend_score_delta", 0),
                                "original_friend_score_delta": original_friend_score_delta,
                                "romance_score_delta": emotion_data.get("romance_score_delta", 0),
                                "original_romance_score_delta": original_romance_score_delta,
                                "decay_ratio": decay_ratio,
                                "start_time": start_time,
                                "end_time": end_time,
                                "original_end_time": original_end_time,
                                "is_ended": is_ended,
                                "update_time": update_time,
                            },
                        )
                        op_logger.info(f"Created new emotion: {emotion_type} for bot {bot_id}")

            await db.commit()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Database error in update_bot_emotions: {str(e)}")
            await db.rollback()
            raise Exception(f"Failed to update bot emotions: {str(e)}") from e

    # LeanCloud conversation mapping operations (related to Bot)
    async def get_bot_by_conversation_id(self, db: AsyncSession, conversation_id: str) -> Optional[str]:
        """Get bot entity_id from LeanCloud conversation ID."""
        try:
            # Create contextualized logger for this operation
            op_logger = bind_context(
                logger, operation="get_bot_by_conversation_id", conversation_id=conversation_id
            )
            op_logger.info("querying_bot_entity_id_by_conversation_id")

            if not conversation_id:
                op_logger.error("empty_conversation_id")
                return None

            result = await db.execute(
                text(
                    "SELECT contact_entity_id FROM conversation_mappings WHERE conversation_id = :conv_id AND im_service_type = :im_service"
                ),
                {"conv_id": conversation_id, "im_service": IMServiceType.LEANCLOUD.value},
            )
            row = result.fetchone()

            if row:
                bot_entity_id = row[0]
                op_logger.info("bot_entity_id_found", bot_entity_id=bot_entity_id)
                return bot_entity_id
            else:
                op_logger.warning("no_bot_entity_id_found")
                return None

        except SQLAlchemyError as e:
            logger.error(
                "database_error_get_bot_by_conversation_id",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                "unexpected_error_get_bot_by_conversation_id",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return None

    async def get_conversation_id_by_bot(self, db: AsyncSession, bot_entity_id: str) -> Optional[str]:
        """Get LeanCloud conversation ID from bot entity_id."""
        try:
            # Create contextualized logger for this operation
            op_logger = bind_context(
                logger, operation="get_conversation_id_by_bot", bot_entity_id=bot_entity_id
            )
            op_logger.info("querying_conversation_id_by_bot_entity_id")

            if not bot_entity_id:
                op_logger.error("empty_bot_entity_id")
                return None

            result = await db.execute(
                text(
                    "SELECT conversation_id FROM conversation_mappings WHERE contact_entity_id = :bot_id AND im_service_type = :im_service"
                ),
                {"bot_id": bot_entity_id, "im_service": IMServiceType.LEANCLOUD.value},
            )
            row = result.fetchone()

            if row:
                conversation_id = row[0]
                op_logger.info("conversation_id_found", conversation_id=conversation_id)
                return conversation_id
            else:
                op_logger.warning("no_conversation_id_found")
                return None

        except SQLAlchemyError as e:
            logger.error(
                "database_error_get_conversation_id_by_bot",
                bot_entity_id=bot_entity_id,
                error=str(e),
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                "unexpected_error_get_conversation_id_by_bot",
                bot_entity_id=bot_entity_id,
                error=str(e),
                exc_info=True,
            )
            return None


# Create instance
bot_crud = CRUDBot(Bot)
