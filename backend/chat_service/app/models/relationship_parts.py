import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Tuple, Dict, Any, Optional

from enums import BufferStatus

logger = logging.getLogger(__name__)


def ensure_datetime(self, dt_value: Any) -> Optional[datetime]:
    """
    Ensures the input value is a datetime object with timezone information

    Args:
        dt_value: Can be a datetime object, string, or None

    Returns:
        A datetime object with timezone information or None
    """
    if dt_value is None:
        return None

    # If already a datetime object
    if isinstance(dt_value, datetime):
        # Ensure it has timezone information
        if not dt_value.tzinfo:
            return dt_value.replace(tzinfo=timezone.utc)
        return dt_value

    # If it's a string, try to convert
    if isinstance(dt_value, str):
        try:
            dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError as e:
            logger.error(f"Error parsing datetime string: {e}")
            return None

    # Other types cannot be processed
    logger.error(f"Unsupported datetime type: {type(dt_value)}")
    return None


def get_passive_score_change(self, days: int) -> Tuple[int, int]:
    """
    Calculates passive score changes based on days since the last interaction,
    simulating relationship "cooling off" or "warming up" towards a neutral state.

    Args:
        days (int): Number of days since the last interaction.

    Returns:
        Tuple[int, int]: A tuple containing the calculated friend_score_change and romance_score_change.
    """
    try:
        if not hasattr(self, "passive_score_config"):
            logger.warning("passive_score_config not found on model instance. Skipping passive change.")
            return 0, 0

        if self.friend_score < 0 or self.romance_score < 0:
            logger.warning(
                f"Friend score or romance score is negative. Skipping passive change. "
                f"friend_score={self.friend_score}, romance_score={self.romance_score}"
            )
            return 0, 0

        # --- Friend Score Change ---
        friend_decay_config = self.passive_score_config.get("friend_decay")
        friend_increase_config = self.passive_score_config.get("friend_increase")
        friend_decay_cool_down = friend_decay_config.get("cool_down_days")
        friend_increase_cool_down = friend_increase_config.get("cool_down_days")

        # Find the threshold for the 'neutral' level
        neutral_threshold = next(
            (
                rel.get("threshold", 0)
                for rel in getattr(self.bot, "friend_config")
                if rel.get("level") == "neutral"
            ),
            0,
        )

        if self.friend_score > neutral_threshold and days > friend_decay_cool_down:
            # The maximum decay cannot go below the trough score
            new_decay = round(self.friend_score_peak * self.friend_passive_ratio - self.friend_score)
            total_decay = friend_decay_config.get("change_rate") * (days - friend_decay_cool_down)
            friend_score_change = min(max(new_decay, total_decay), 0)
        elif self.friend_score < neutral_threshold and days > friend_increase_cool_down:
            # Score increases towards the neutral threshold
            new_increase = neutral_threshold - self.friend_score
            total_increase = friend_increase_config.get("change_rate") * (days - friend_increase_cool_down)
            friend_score_change = max(min(new_increase, total_increase), 0)
        else:
            friend_score_change = 0

        # --- Romance Score Change ---
        romance_config = self.passive_score_config.get("romance_decay")
        romance_cool_down = romance_config.get("cool_down_days")

        if days > romance_cool_down:
            # Romance score only decays, it does not increase passively
            new_decay = round(self.romance_score_peak * self.romance_passive_ratio - self.romance_score)
            total_decay = romance_config.get("change_rate") * (days - romance_cool_down)
            romance_score_change = min(max(new_decay, total_decay), 0)
        else:
            romance_score_change = 0

        logger.debug(
            f"get_passive_score_change: Passive score change after {days} days: "
            f"friend={friend_score_change}, romance={romance_score_change}"
        )
        return friend_score_change, romance_score_change
    except Exception as e:
        logger.error(f"Error calculating passive score changes: {e}", exc_info=True)
        return 0, 0


def calculate_passive_scores(self) -> None:
    """Calculate emotions and relationship scores based on current emotions and time factors

    This method processes the current emotions, calculating score changes based on:
    1. Emotion decay over time (percentage of emotion duration)
    2. Passive relationship changes when emotion has ended
    3. Updates bot scores and emotions as needed
    4. Updates last_chat_time to current time
    """
    try:
        now = datetime.now(timezone.utc)

        # Initialize emotion and passive score changes
        emotion_f_score_delta = 0
        emotion_r_score_delta = 0

        # Use helper function to process last_chat_time
        last_chat_time = self._ensure_datetime(getattr(self.bot, "last_chat_time", None))

        # Calculate days passed since last_chat_time
        days_passed = 0
        if last_chat_time:
            days_passed = (now - last_chat_time).days

        # Make sure each emotion type only appears once
        emotion_type_counter = {}

        # Process each emotion
        for emotion_type, emotion_data in self.emotions.items():
            try:
                # Check if the emotion type has already been processed
                if emotion_type in emotion_type_counter:
                    logger.error(
                        f"Error: Emotion type {emotion_type} appears multiple times for bot {self.bot.id}. "
                        f"Each emotion type should only appear once."
                    )
                    continue  # Skip this emotion
                else:
                    emotion_type_counter[emotion_type] = 1

                # Unified validation for emotion data completeness
                required_fields = [
                    "start_time",
                    "end_time",
                    "decay_ratio",
                    "friend_score_delta",
                    "original_friend_score_delta",
                    "romance_score_delta",
                    "original_romance_score_delta",
                ]

                missing_fields = [field for field in required_fields if emotion_data.get(field) is None]
                if missing_fields:
                    logger.warning(
                        f"Incomplete emotion data for {emotion_type} (bot {self.bot.id}): missing {', '.join(missing_fields)}"
                    )
                    continue

                # Process specific emotion types
                if emotion_type == "anger":
                    # Skip emotions that have ended
                    if emotion_data.get("is_ended", False):
                        logger.info(f"Skipping ended emotion {emotion_type} for bot {self.bot.id}")
                        continue

                    # Process time fields
                    start_time = self._ensure_datetime(emotion_data["start_time"])
                    end_time = self._ensure_datetime(emotion_data["end_time"])

                    # Verify if last_chat_time is within the emotion time range
                    if last_chat_time and last_chat_time > end_time:
                        logger.warning(
                            f"Emotion {emotion_type} outside valid time range for bot {self.bot.id}: "
                            f"last_chat={last_chat_time}, emotion={start_time} to {end_time}"
                        )
                        continue

                    # Validate total duration validity
                    total_duration = (end_time - start_time).total_seconds()
                    if total_duration <= 0:
                        logger.warning(
                            f"Invalid emotion duration for {emotion_type} (bot {self.bot.id}): {total_duration}s"
                        )
                        continue

                    # Calculate elapsed time percentage
                    if now >= end_time:
                        time_percentage = 1.0
                    else:
                        elapsed_time = (now - start_time).total_seconds()
                        time_percentage = min(1.0, max(0.0, elapsed_time / total_duration))

                    # Get original score deltas and decay ratio
                    decay_ratio = emotion_data["decay_ratio"]
                    original_f_score_delta = emotion_data["original_friend_score_delta"]
                    original_r_score_delta = emotion_data["original_romance_score_delta"]
                    f_score_delta = emotion_data["friend_score_delta"]
                    r_score_delta = emotion_data["romance_score_delta"]

                    if (
                        original_f_score_delta > 0
                        or original_r_score_delta > 0
                        or f_score_delta > 0
                        or r_score_delta > 0
                    ):
                        logger.warning(
                            f"Emotion {emotion_type} has a positive original or current score delta. This is not allowed. "
                            f"original_f_score_delta: {original_f_score_delta}, original_r_score_delta: {original_r_score_delta}, "
                            f"f_score_delta: {f_score_delta}, r_score_delta: {r_score_delta}"
                        )
                        continue

                    if f_score_delta < original_f_score_delta:
                        logger.warning(
                            f"Emotion {emotion_type} has a positive current score delta. This is not allowed. "
                            f"f_score_delta: {f_score_delta}, original_f_score_delta: {original_f_score_delta}"
                        )
                        f_score_delta = original_f_score_delta

                    if r_score_delta < original_r_score_delta:
                        logger.warning(
                            f"Emotion {emotion_type} has a positive current score delta. This is not allowed. "
                            f"r_score_delta: {r_score_delta}, original_r_score_delta: {original_r_score_delta}"
                        )
                        r_score_delta = original_r_score_delta

                    if decay_ratio > 1:
                        logger.warning(
                            f"Emotion {emotion_type} has a decay ratio greater than 1. This is not allowed. decay_ratio: {decay_ratio}"
                        )
                        decay_ratio = self.emotion_calculation_rules.get("decay_ratio", 2)

                    # Calculate emotion impact on scores (negative for anger)
                    anger_f_score_delta = round(
                        f_score_delta - original_f_score_delta * decay_ratio * time_percentage
                    )
                    anger_r_score_delta = round(
                        r_score_delta - original_r_score_delta * decay_ratio * time_percentage
                    )
                    emotion_f_score_delta += min(anger_f_score_delta, f_score_delta)
                    emotion_r_score_delta += min(anger_r_score_delta, r_score_delta)

                    # Check if emotion has ended
                    if anger_f_score_delta >= 0 and anger_r_score_delta >= 0:
                        emotion_data["is_ended"] = True
                        logger.info(f"Emotion {emotion_type} has ended for bot {self.bot.id}")
                    elif now > end_time or emotion_data.get("emotion_score") <= 0:
                        # Calculate days since emotion ended
                        days_passed = (now - end_time).days

                        # Mark emotion as ended in memory
                        emotion_data["is_ended"] = True
                        logger.info(f"Marked emotion {emotion_type} as ended for bot {self.bot.id}")

                if emotion_f_score_delta != 0 or emotion_r_score_delta != 0:
                    logger.debug(
                        f"The {emotion_type} score changes for bot {self.bot.id}: "
                        f"friend={emotion_f_score_delta}, romance={emotion_r_score_delta}"
                    )
            except Exception as e:
                logger.error(f"Error processing emotion {emotion_type}: {e}", exc_info=True)

        # Get passive score changes
        passive_f_score_change, passive_r_score_change = self._get_passive_score_change(days_passed)

        # Update calculated values, ensuring the delta is rounded
        self.friend_score_calc = max(
            0, round(self.friend_score + emotion_f_score_delta + passive_f_score_change)
        )
        self.romance_score_calc = max(
            0,
            round(self.romance_score + emotion_r_score_delta + passive_r_score_change),
        )
        self.friend_score = max(0, round(self.friend_score + passive_f_score_change))
        self.romance_score = max(0, round(self.romance_score + passive_r_score_change))

        # Update peak and trough values
        self.friend_score_peak = max(self.friend_score_peak, self.friend_score)
        self.friend_score_trough = min(self.friend_score_trough, self.friend_score)
        self.romance_score_peak = max(self.romance_score_peak, self.romance_score)

        logger.debug(
            f"Score changes for bot {self.bot.id}: "
            f"friend_score={self.friend_score}, friend_score_calc={self.friend_score_calc} "
            f"(anger={emotion_f_score_delta}, passive={passive_f_score_change}), "
            f"romance_score={self.romance_score}, romance_score_calc={self.romance_score_calc} "
            f"(anger={emotion_r_score_delta}, passive={passive_r_score_change})"
        )

        # Update last_chat_time in memory
        try:
            current_time = datetime.now(timezone.utc)
            if hasattr(self.bot, "last_chat_time"):
                self.bot.last_chat_time = current_time
                self.last_chat_time = current_time  # Also update the direct attribute on self

            logger.debug(f"Updated last_chat_time to {current_time} for bot {self.bot.id}")
            # DB update removed, will be persisted later.
        except Exception as e:
            logger.error(
                f"Error updating last_chat_time for bot {self.bot.id}: {str(e)}",
                exc_info=True,
            )

    except Exception as e:
        logger.error(f"Error calculating emotions and scores: {str(e)}", exc_info=True)


def calculate_anger_score(self, response_content: str) -> None:
    """Process anger emotion from response content and update scores accordingly.

    This method focuses exclusively on processing anger emotions:
    1. Extracts anger score from response content
    2. Calculates appropriate emotion level based on configured thresholds
    3. Computes score deltas using a tiered calculation system
    4. Sets emotion duration based on anger level
    5. Updates or creates anger emotion records

    Formulas:
    - Level 1 score delta: friend/romance_score * anger_score * multiplier
    - Level 2 score delta: friend/romance_score * level1_max * multiplier +
                          friend/romance_score * (anger_score - level1_max) * multiplier
    - Level 3 score delta: friend/romance_score * level1_max * multiplier +
                          friend/romance_score * (level2_max - level1_max) * multiplier +
                          friend/romance_score * (anger_score - level2_max) * multiplier

    - Level 1 duration: start_time + (anger_score * 120 / friend_score_neg_k * duration_multiplier) minutes ± random_factor
    - Level 2 duration: start_time + ((anger_score - level1_max) * 120 / friend_score_neg_k * duration_multiplier) minutes ± random_factor
    - Level 3 duration: start_time + ((anger_score - level2_max) * 120 / friend_score_neg_k * duration_multiplier) minutes ± random_factor
    """
    try:
        # Parse JSON response
        response_data = json.loads(response_content)

        # Check if emotions data exists in the response
        if "emotions" not in response_data:
            logger.debug("No emotions data in response")
            return

        # Extract anger score from emotions data
        emotions_data = response_data.get("emotions", {})
        current_anger_score = emotions_data.get("anger", 0)

        # If no anger, nothing to process
        if current_anger_score <= 0:
            logger.debug("No anger emotion to process")
            return

        # Get relationship scores from response
        friend_score_change = response_data.get("friend_score", 0)
        romance_score_change = response_data.get("romance_score", 0)

        # Get bot configuration values
        emotions_config = getattr(self.bot, "emotions_config", {})
        friend_score_neg_k = getattr(self.bot, "friend_score_neg_k", 100)

        # Get anger thresholds from config
        anger_thresholds = emotions_config.get("anger", [])

        # Get anger configuration from emotion_config
        anger_config = self.emotion_calculation_rules.get("anger", {})

        # Sort thresholds by level
        sorted_thresholds = sorted(anger_thresholds, key=lambda x: x.get("level", 0))

        # Determine anger level based on current score
        current_level = 0
        level1_max = 0
        level2_max = 0

        for threshold in sorted_thresholds:
            threshold_value = threshold.get("threshold", 0)
            level = threshold.get("level", 0)

            if current_anger_score >= threshold_value:
                current_level = level

            # Store threshold values for level calculations
            if level == 1:
                level1_max = threshold_value
            elif level == 2:
                level2_max = threshold_value

        # Set decay ratio based on anger level using config
        decay_ratios = anger_config.get("decay_ratios", {1: 0.5, 2: 0.4, 3: 0.2})
        decay_ratio = decay_ratios.get(current_level, 0.5)

        # Calculate score deltas based on tiered system
        friend_score_delta = 0
        romance_score_delta = 0

        # Get score multipliers from config
        score_multipliers = anger_config.get("score_multipliers", {1: 2, 2: 2, 3: 10})

        # Calculate score deltas based on anger level
        if current_level == 1:
            level1_multiplier = score_multipliers.get(1, 2)
            friend_score_delta = friend_score_change * current_anger_score * level1_multiplier
            romance_score_delta = romance_score_change * current_anger_score * level1_multiplier
        elif current_level == 2:
            level1_multiplier = score_multipliers.get(1, 2)
            level2_multiplier = score_multipliers.get(2, 2)
            friend_score_delta = (
                friend_score_change * level1_max * level1_multiplier
                + friend_score_change * (current_anger_score - level1_max) * level2_multiplier
            )
            romance_score_delta = (
                romance_score_change * level1_max * level1_multiplier
                + romance_score_change * (current_anger_score - level1_max) * level2_multiplier
            )
        elif current_level == 3:
            level1_multiplier = score_multipliers.get(1, 2)
            level2_multiplier = score_multipliers.get(2, 2)
            level3_multiplier = score_multipliers.get(3, 10)
            friend_score_delta = (
                friend_score_change * level1_max * level1_multiplier
                + friend_score_change * (level2_max - level1_max) * level2_multiplier
                + friend_score_change * (current_anger_score - level2_max) * level3_multiplier
            )
            romance_score_delta = (
                romance_score_change * level1_max * level1_multiplier
                + romance_score_change * (level2_max - level1_max) * level2_multiplier
                + romance_score_change * (current_anger_score - level2_max) * level3_multiplier
            )

        # Calculate duration based on anger level
        now = datetime.now(timezone.utc)
        end_time = now

        # Get duration multipliers and random range from config
        duration_multipliers = anger_config.get("duration_multipliers", {1: 10, 2: 180, 3: 840})
        duration_random_range = anger_config.get("duration_random_range", (0.9, 1.1))

        # Apply duration formula based on level using config duration multipliers
        if current_level > 0:
            duration_multiplier = duration_multipliers.get(current_level, 10)

            # Calculate base duration in minutes
            if current_level == 1:
                base_minutes = round(current_anger_score * 120 / friend_score_neg_k * duration_multiplier)
            elif current_level == 2:
                base_minutes = round(
                    (current_anger_score - level1_max) * 120 / friend_score_neg_k * duration_multiplier
                )
            elif current_level == 3:
                base_minutes = round(
                    (current_anger_score - level2_max) * 120 / friend_score_neg_k * duration_multiplier
                )
            else:
                base_minutes = 60  # Default 1 hour

            # Apply random factor from config range
            random_factor = random.uniform(*duration_random_range)
            minutes = base_minutes * random_factor
            end_time = now + timedelta(minutes=minutes)

        # Check if we already have an anger emotion
        existing_anger = self.emotions.get("anger", {})
        original_anger_score = existing_anger.get("original_emotion_score", 0)

        # Prepare updated emotion data
        updated_emotion: Dict[str, Any] = {}

        if original_anger_score > 0:
            # Anger already exists, update it
            if current_anger_score < original_anger_score:
                # Anger is decreasing
                ratio = current_anger_score / original_anger_score
                original_f_score_delta = existing_anger.get("original_friend_score_delta", 0)
                original_r_score_delta = existing_anger.get("original_romance_score_delta", 0)

                # Update score deltas proportionally and round to the nearest integer
                friend_score_delta = round(original_f_score_delta * ratio)
                romance_score_delta = round(original_r_score_delta * ratio)

                # Adjust end time if ratio exceeds decay ratio
                original_end_time = self._ensure_datetime(existing_anger.get("original_end_time", ""))
                start_time = self._ensure_datetime(existing_anger.get("start_time", ""))

                if original_end_time and start_time and ratio > decay_ratio:
                    # Calculate new duration as a fraction of original
                    original_duration = (original_end_time - start_time).total_seconds()
                    new_duration = original_duration * (decay_ratio - 1 + ratio)
                    end_time = start_time + timedelta(seconds=new_duration)

                updated_emotion = {
                    "anger": {
                        **existing_anger,
                        "emotion_score": current_anger_score,
                        "friend_score_delta": friend_score_delta,
                        "romance_score_delta": romance_score_delta,
                        "end_time": end_time.isoformat(),
                        "update_time": now.isoformat(),
                    }
                }
            else:
                # Anger is increasing or unchanged - create new record with new original values
                updated_emotion = {
                    "anger": {
                        "emotion_score": current_anger_score,
                        "original_emotion_score": current_anger_score,
                        "emotion_level": current_level,
                        "friend_score_delta": friend_score_delta,
                        "original_friend_score_delta": friend_score_delta,
                        "romance_score_delta": romance_score_delta,
                        "original_romance_score_delta": romance_score_delta,
                        "decay_ratio": decay_ratio,
                        "start_time": now.isoformat(),
                        "end_time": end_time.isoformat(),
                        "original_end_time": end_time.isoformat(),
                        "is_ended": False,
                        "update_time": now.isoformat(),
                    }
                }
        else:
            # New anger emotion
            updated_emotion = {
                "anger": {
                    "emotion_score": current_anger_score,
                    "original_emotion_score": current_anger_score,
                    "emotion_level": current_level,
                    "friend_score_delta": friend_score_delta,
                    "original_friend_score_delta": friend_score_delta,
                    "romance_score_delta": romance_score_delta,
                    "original_romance_score_delta": romance_score_delta,
                    "decay_ratio": decay_ratio,
                    "start_time": now.isoformat(),
                    "end_time": end_time.isoformat(),
                    "original_end_time": end_time.isoformat(),
                    "is_ended": False,
                    "update_time": now.isoformat(),
                }
            }

        # Update local emotions data
        self.emotions.update(updated_emotion)

        # DB update removed, will be persisted later.
        logger.debug(
            f"Updated anger emotion for bot {self.bot.id}: level={current_level}, score={current_anger_score}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing response JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing anger emotion: {str(e)}", exc_info=True)


def refresh_relationship(self) -> None:
    """
    Refreshes the bot's relationship type, level, and style based on current scores and configurations.
    The changes are applied to the bot instance and are not immediately persisted to the database.
    1. Determines the best friend and romance relationships based on calculated scores.
    2. Selects a primary relationship based on priority.
    3. Applies override configurations if conditions are met.
    4. Updates the bot's relationship attributes in memory.
    """
    logger.debug(
        f"Refreshing relationship for bot {self.bot.entity_id} "
        f"with F_calc:{self.friend_score_calc}, R_calc:{self.romance_score_calc}"
    )

    original_rel_type = self.relationship_type
    original_rel_level = self.relationship_level

    # Get current relationship levels based on scores
    current_friend_rel = self._get_level_from_score(self.friend_score_calc, "friend")
    current_romance_rel = self._get_level_from_score(self.romance_score_calc, "romance")

    # Apply hysteresis to determine the new stable level
    self.friend_level, self.friend_buffer_status = self._apply_buffer(
        current_rel=current_friend_rel,
        stable_level_name=self.friend_level,
        buffer_status=self.friend_buffer_status,
        score=self.friend_score_calc,
        level_up_buffer=self.friend_level_up_buffer,
        level_down_buffer=self.friend_level_down_buffer,
        relationship_config=self.bot.friend_config,
        rel_type="friend",
    )

    self.romance_level, self.romance_buffer_status = self._apply_buffer(
        current_rel=current_romance_rel,
        stable_level_name=self.romance_level,
        buffer_status=self.romance_buffer_status,
        score=self.romance_score_calc,
        level_up_buffer=self.romance_level_up_buffer,
        level_down_buffer=self.romance_level_down_buffer,
        relationship_config=self.bot.romance_config,
        rel_type="romance",
    )

    # Determine the primary relationship based on priority
    friend_rel_obj = self._get_level_by_name(self.friend_level, "friend")
    romance_rel_obj = self._get_level_by_name(self.romance_level, "romance")

    primary_rel = None
    if friend_rel_obj and romance_rel_obj:
        primary_rel = (
            friend_rel_obj
            if friend_rel_obj.get("priority", 0) >= romance_rel_obj.get("priority", 0)
            else romance_rel_obj
        )
    elif friend_rel_obj:
        primary_rel = friend_rel_obj
    elif romance_rel_obj:
        primary_rel = romance_rel_obj

    # Update relationship attributes
    if primary_rel:
        self.relationship_type = primary_rel.get("type", self.relationship_type)
        self.relationship_level = primary_rel.get("level", self.relationship_level)
        self.relationship_style = primary_rel.get("style", self.relationship_style)
    else:
        # Fallback to original if no relationship could be determined
        self.relationship_type = original_rel_type
        self.relationship_level = original_rel_level

    logger.info(
        f"Relationship updated for bot {self.bot.entity_id}: "
        f"Type='{self.relationship_type}', Level='{self.relationship_level}', "
        f"Friend Level='{self.friend_level}' (Buffer: {self.friend_buffer_status}), "
        f"Romance Level='{self.romance_level}' (Buffer: {self.romance_buffer_status})."
    )


def get_level_from_score(self, score: int, rel_type: str) -> Optional[Dict[str, Any]]:
    """Gets the relationship level object corresponding to a given score."""
    config = getattr(self.bot, f"{rel_type}_config", [])
    if not config or not isinstance(config, list):
        return None

    applicable_rels = [rel for rel in config if isinstance(rel, dict) and score >= rel.get("threshold", 0)]
    if not applicable_rels:
        return None

    rel = max(applicable_rels, key=lambda x: x["threshold"])
    rel["type"] = rel_type
    return rel


def get_level_by_name(self, level_name: Optional[str], rel_type: str) -> Optional[Dict[str, Any]]:
    """Gets the relationship level object by its name."""
    if not level_name:
        return None
    config = getattr(self.bot, f"{rel_type}_config", [])
    if not config:
        return None

    for rel in config:
        if rel.get("level") == level_name:
            rel["type"] = rel_type
            return rel
    return None


def apply_buffer(
    self,
    current_rel,
    stable_level_name,
    buffer_status,
    score,
    level_up_buffer,
    level_down_buffer,
    relationship_config,
    rel_type,
):
    """Applies hysteresis to a relationship level transition."""
    stable_rel = self._get_level_by_name(stable_level_name, rel_type)

    if not stable_rel:  # No stable level yet, so set it
        return (current_rel.get("level") if current_rel else None), BufferStatus.NONE.value

    if not current_rel:  # No current level for the score, weird state
        return stable_level_name, buffer_status

    current_threshold = current_rel.get("threshold", 0)
    stable_threshold = stable_rel.get("threshold", 0)

    new_level = stable_level_name
    new_buffer_status = buffer_status

    if current_threshold > stable_threshold:  # Potential level up
        if buffer_status == BufferStatus.LEVEL_UP_BUFFER.value:
            if score >= current_threshold:
                new_level = current_rel.get("level")
                new_buffer_status = BufferStatus.NONE.value
        elif score >= stable_threshold * level_up_buffer:
            new_level = current_rel.get("level")
            new_buffer_status = BufferStatus.NONE.value
        elif score >= stable_threshold:
            new_buffer_status = BufferStatus.LEVEL_UP_BUFFER.value

    elif current_threshold < stable_threshold:  # Potential level down
        if buffer_status == BufferStatus.LEVEL_DOWN_BUFFER.value:
            if score < current_threshold:
                new_level = current_rel.get("level")
                new_buffer_status = BufferStatus.NONE.value
        elif score < stable_threshold * level_down_buffer:
            new_level = current_rel.get("level")
            new_buffer_status = BufferStatus.NONE.value
        elif score < stable_threshold:
            new_buffer_status = BufferStatus.LEVEL_DOWN_BUFFER.value
    else:  # Score is within the same level
        new_buffer_status = BufferStatus.NONE.value

    return new_level, new_buffer_status
