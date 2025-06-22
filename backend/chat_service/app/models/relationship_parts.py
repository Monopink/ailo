import random
from datetime import datetime, timedelta, timezone
from typing import Tuple, Dict, Any, Optional

from enums import BufferStatus, EmotionType, FriendLevel, RelationshipType


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
            self.logger.error("datetime_parse_error", error=str(e))
            return None

    # Other types cannot be processed
    self.logger.error("unsupported_datetime_type", type=str(type(dt_value)))
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
            self.logger.warning(
                "passive_score_config_missing",
                message="Config not found on model instance. Skipping passive change.",
            )
            return 0, 0

        try:
            # Use direct access for internal configuration. A KeyError indicates a critical config error.
            friend_decay_config = self.passive_score_config["friend_decay"]
            friend_increase_config = self.passive_score_config["friend_increase"]
            romance_decay_config = self.passive_score_config["romance_decay"]

            friend_decay_cool_down = friend_decay_config["cool_down_days"]
            friend_increase_cool_down = friend_increase_config["cool_down_days"]
            friend_decay_change_rate = friend_decay_config["change_rate"]
            friend_increase_change_rate = friend_increase_config["change_rate"]

            romance_cool_down = romance_decay_config["cool_down_days"]
            romance_decay_change_rate = romance_decay_config["change_rate"]
        except KeyError as e:
            self.logger.error(
                "passive_score_config_key_missing",
                error=f"Key {e} is missing from passive_score_config",
                exc_info=True,
            )
            return 0, 0

        if self.friend_score < 0 or self.romance_score < 0:
            self.logger.warning(
                "negative_relationship_scores",
                friend_score=self.friend_score,
                romance_score=self.romance_score,
                message="Skipping passive change",
            )
            return 0, 0

        # --- Friend Score Change ---
        # Find the threshold for the 'neutral' level
        neutral_threshold = next(
            (
                rel["threshold"]
                for rel in getattr(self.bot, "friend_config")
                if rel.get("level") == FriendLevel.NEUTRAL.value
            ),
            0,
        )

        if self.friend_score > neutral_threshold and days > friend_decay_cool_down:
            # The maximum decay cannot go below the trough score
            new_decay = round(self.friend_score_peak * self.friend_passive_ratio - self.friend_score)
            total_decay = friend_decay_change_rate * (days - friend_decay_cool_down)
            friend_score_change = min(max(new_decay, total_decay), 0)
        elif self.friend_score < neutral_threshold and days > friend_increase_cool_down:
            # Score increases towards the neutral threshold
            new_increase = neutral_threshold - self.friend_score
            total_increase = friend_increase_change_rate * (days - friend_increase_cool_down)
            friend_score_change = max(min(new_increase, total_increase), 0)
        else:
            friend_score_change = 0

        # --- Romance Score Change ---
        if days > romance_cool_down:
            # Romance score only decays, it does not increase passively
            new_decay = round(self.romance_score_peak * self.romance_passive_ratio - self.romance_score)
            total_decay = romance_decay_change_rate * (days - romance_cool_down)
            romance_score_change = min(max(new_decay, total_decay), 0)
        else:
            romance_score_change = 0

        self.logger.info(
            "passive_score_change_calculated",
            days=days,
            friend_change=friend_score_change,
            romance_change=romance_score_change,
        )
        return friend_score_change, romance_score_change
    except Exception as e:
        self.logger.error("passive_score_calculation_error", error=str(e), exc_info=True)
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
        emotion_fnd_sc_delta = 0
        emotion_rom_sc_delta = 0

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
                    self.logger.error(
                        "duplicate_emotion_type",
                        emotion_type=emotion_type,
                        message="Each emotion type should only appear once",
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
                    self.logger.warning(
                        "incomplete_emotion_data",
                        emotion_type=emotion_type,
                        missing_fields=missing_fields,
                    )
                    continue

                # Process specific emotion types
                if emotion_type == EmotionType.ANGER.value:
                    # Skip emotions that have ended
                    if emotion_data.get("is_ended", False):
                        self.logger.info("skipping_ended_emotion", emotion_type=emotion_type)
                        continue

                    # Process time fields
                    start_time = self._ensure_datetime(emotion_data["start_time"])
                    end_time = self._ensure_datetime(emotion_data["end_time"])

                    # Verify if last_chat_time is within the emotion time range
                    if last_chat_time and last_chat_time > end_time:
                        self.logger.warning(
                            "emotion_outside_valid_range",
                            emotion_type=emotion_type,
                            last_chat_time=last_chat_time.isoformat(),
                            emotion_start=start_time.isoformat(),
                            emotion_end=end_time.isoformat(),
                        )
                        continue

                    # Validate total duration validity
                    total_duration = (end_time - start_time).total_seconds()
                    if total_duration <= 0:
                        self.logger.warning(
                            "invalid_emotion_duration", emotion_type=emotion_type, duration=total_duration
                        )
                        continue

                    # Calculate elapsed time percentage
                    elapsed_time = (now - start_time).total_seconds()
                    time_percentage = min(1.0, max(0.0, elapsed_time / total_duration))

                    # Get original score deltas and decay ratio
                    decay_ratio = emotion_data["decay_ratio"]
                    original_fnd_sc_delta = emotion_data["original_friend_score_delta"]
                    original_rom_sc_delta = emotion_data["original_romance_score_delta"]
                    fnd_sc_delta = emotion_data["friend_score_delta"]
                    rom_sc_delta = emotion_data["romance_score_delta"]

                    if (
                        original_fnd_sc_delta > 0
                        or original_rom_sc_delta > 0
                        or fnd_sc_delta > 0
                        or rom_sc_delta > 0
                    ):
                        self.logger.warning(
                            "positive_emotion_delta_not_allowed",
                            emotion_type=emotion_type,
                            original_fnd_sc_delta=original_fnd_sc_delta,
                            original_rom_sc_delta=original_rom_sc_delta,
                            fnd_sc_delta=fnd_sc_delta,
                            rom_sc_delta=rom_sc_delta,
                        )
                        continue

                    if fnd_sc_delta < original_fnd_sc_delta:
                        self.logger.warning(
                            "invalid_friend_score_delta",
                            emotion_type=emotion_type,
                            fnd_sc_delta=fnd_sc_delta,
                            original_fnd_sc_delta=original_fnd_sc_delta,
                        )
                        fnd_sc_delta = original_fnd_sc_delta

                    if rom_sc_delta < original_rom_sc_delta:
                        self.logger.warning(
                            "invalid_romance_score_delta",
                            emotion_type=emotion_type,
                            rom_sc_delta=rom_sc_delta,
                            original_rom_sc_delta=original_rom_sc_delta,
                        )
                        rom_sc_delta = original_rom_sc_delta

                    if decay_ratio > 1:
                        self.logger.warning(
                            "invalid_decay_ratio", emotion_type=emotion_type, decay_ratio=decay_ratio
                        )
                        decay_ratio = self.emotion_calculation_rules.get("decay_ratio", 2)

                    # Calculate emotion impact on scores (negative for anger)
                    anger_fnd_sc_delta = round(
                        fnd_sc_delta - original_fnd_sc_delta * decay_ratio * time_percentage
                    )
                    anger_rom_sc_delta = round(
                        rom_sc_delta - original_rom_sc_delta * decay_ratio * time_percentage
                    )
                    emotion_fnd_sc_delta += min(anger_fnd_sc_delta, fnd_sc_delta)
                    emotion_rom_sc_delta += min(anger_rom_sc_delta, rom_sc_delta)

                    # Check if emotion has ended
                    if anger_fnd_sc_delta >= 0 and anger_rom_sc_delta >= 0:
                        emotion_data["is_ended"] = True
                        self.logger.info("emotion_ended_naturally", emotion_type=emotion_type)
                    elif now > end_time or emotion_data.get("emotion_score") <= 0:
                        # Calculate days since emotion ended
                        days_passed = (now - end_time).days

                        # Mark emotion as ended in memory
                        emotion_data["is_ended"] = True
                        self.logger.info("emotion_marked_as_ended", emotion_type=emotion_type)

                if emotion_fnd_sc_delta != 0 or emotion_rom_sc_delta != 0:
                    self.logger.info(
                        "emotion_score_changes",
                        emotion_type=emotion_type,
                        friend_delta=emotion_fnd_sc_delta,
                        romance_delta=emotion_rom_sc_delta,
                    )
            except Exception as e:
                self.logger.error(
                    "emotion_processing_error", emotion_type=emotion_type, error=str(e), exc_info=True
                )

        # Get passive score changes
        passive_fnd_sc_change, passive_rom_sc_change = self._get_passive_score_change(days_passed)

        # Update calculated values, ensuring the delta is rounded
        self.friend_score_calc = max(
            0, round(self.friend_score + emotion_fnd_sc_delta + passive_fnd_sc_change)
        )
        self.romance_score_calc = max(
            0,
            round(self.romance_score + emotion_rom_sc_delta + passive_rom_sc_change),
        )
        self.friend_score = max(0, round(self.friend_score + passive_fnd_sc_change))
        self.romance_score = max(0, round(self.romance_score + passive_rom_sc_change))

        # Update peak and trough values
        self.friend_score_peak = max(self.friend_score_peak, self.friend_score)
        self.friend_score_trough = min(self.friend_score_trough, self.friend_score)
        self.romance_score_peak = max(self.romance_score_peak, self.romance_score)

        self.logger.info(
            "relationship_scores_updated",
            friend_score=self.friend_score,
            friend_score_calc=self.friend_score_calc,
            emotion_friend_delta=emotion_fnd_sc_delta,
            passive_friend_delta=passive_fnd_sc_change,
            romance_score=self.romance_score,
            romance_score_calc=self.romance_score_calc,
            emotion_romance_delta=emotion_rom_sc_delta,
            passive_romance_delta=passive_rom_sc_change,
        )

        # Update last_chat_time in memory
        try:
            current_time = datetime.now(timezone.utc)
            if hasattr(self.bot, "last_chat_time"):
                self.bot.last_chat_time = current_time
                self.last_chat_time = current_time  # Also update the direct attribute on self

            self.logger.info("last_chat_time_updated", timestamp=current_time.isoformat())
            # DB update removed, will be persisted later.
        except Exception as e:
            self.logger.error("error_updating_last_chat_time", error=str(e), exc_info=True)

    except Exception as e:
        self.logger.error("error_calculating_emotions_scores", error=str(e), exc_info=True)


def get_level_from_score(self, score: int, rel_type: str) -> Optional[Dict[str, Any]]:
    """Gets the relationship level object corresponding to a given score."""
    config = getattr(self.bot, f"{rel_type}_config", [])
    if not config or not isinstance(config, list):
        return None

    applicable_rels = [rel for rel in config if isinstance(rel, dict) and score >= rel["threshold"]]
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
        if rel["level"] == level_name:
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

    current_threshold = current_rel["threshold"]
    stable_threshold = stable_rel["threshold"]

    new_level = stable_level_name
    new_buffer_status = buffer_status

    if current_threshold > stable_threshold:  # Potential level up
        if buffer_status == BufferStatus.LEVEL_UP_BUFFER.value:
            if score >= current_threshold:
                new_level = current_rel["level"]
                new_buffer_status = BufferStatus.NONE.value
        elif score >= stable_threshold * level_up_buffer:
            new_level = current_rel["level"]
            new_buffer_status = BufferStatus.NONE.value
        elif score >= stable_threshold:
            new_buffer_status = BufferStatus.LEVEL_UP_BUFFER.value

    elif current_threshold < stable_threshold:  # Potential level down
        if buffer_status == BufferStatus.LEVEL_DOWN_BUFFER.value:
            if score < current_threshold:
                new_level = current_rel["level"]
                new_buffer_status = BufferStatus.NONE.value
        elif score < stable_threshold * level_down_buffer:
            new_level = current_rel["level"]
            new_buffer_status = BufferStatus.NONE.value
        elif score < stable_threshold:
            new_buffer_status = BufferStatus.LEVEL_DOWN_BUFFER.value
    else:  # Score is within the same level
        new_buffer_status = BufferStatus.NONE.value

    return new_level, new_buffer_status


def refresh_relationship(self) -> None:
    """
    Refreshes the bot's relationship type, level, and style based on current scores and configurations.
    The changes are applied to the bot instance and are not immediately persisted to the database.
    1. Determines the best friend and romance relationships based on calculated scores.
    2. Selects a primary relationship based on priority.
    3. Applies override configurations if conditions are met.
    4. Updates the bot's relationship attributes in memory.
    """
    self.logger.info(
        "refreshing_relationship",
        friend_score_calc=self.friend_score_calc,
        romance_score_calc=self.romance_score_calc,
    )

    # Get original relationship type, use self.bot.relationship_type if self.relationship_type doesn't exist
    original_rel_type = getattr(self, "relationship_type", self.bot.relationship_type)
    original_rel_level = getattr(self, "relationship_level", self.bot.relationship_level)

    # Get current relationship levels based on scores
    current_friend_rel = self._get_level_from_score(self.friend_score_calc, RelationshipType.FRIEND.value)
    current_romance_rel = self._get_level_from_score(
        self.romance_score_calc, RelationshipType.ROMANCE.value
    )

    self.logger.debug(
        "current_relationship_levels",
        current_friend_rel=current_friend_rel,
        current_romance_rel=current_romance_rel,
    )

    # Apply hysteresis to determine the new stable level
    self.friend_level, self.friend_buffer_status = self._apply_buffer(
        current_rel=current_friend_rel,
        stable_level_name=self.friend_level,
        buffer_status=self.friend_buffer_status,
        score=self.friend_score_calc,
        level_up_buffer=self.friend_level_up_buffer,
        level_down_buffer=self.friend_level_down_buffer,
        relationship_config=self.bot.friend_config,
        rel_type=RelationshipType.FRIEND.value,
    )

    self.romance_level, self.romance_buffer_status = self._apply_buffer(
        current_rel=current_romance_rel,
        stable_level_name=self.romance_level,
        buffer_status=self.romance_buffer_status,
        score=self.romance_score_calc,
        level_up_buffer=self.romance_level_up_buffer,
        level_down_buffer=self.romance_level_down_buffer,
        relationship_config=self.bot.romance_config,
        rel_type=RelationshipType.ROMANCE.value,
    )

    self.logger.debug(
        "after_buffer_application",
        friend_level=self.friend_level,
        friend_buffer_status=self.friend_buffer_status,
        romance_level=self.romance_level,
        romance_buffer_status=self.romance_buffer_status,
    )

    # Determine the primary relationship based on priority
    friend_rel_obj = self._get_level_by_name(self.friend_level, RelationshipType.FRIEND.value)
    romance_rel_obj = self._get_level_by_name(self.romance_level, RelationshipType.ROMANCE.value)

    self.logger.debug(
        "relationship_objects", friend_rel_obj=friend_rel_obj, romance_rel_obj=romance_rel_obj
    )

    primary_rel = None
    if friend_rel_obj and romance_rel_obj:
        # 'priority' is a mandatory field for comparing relationships.
        # Direct access ensures that a misconfiguration will raise an error immediately.
        friend_priority = friend_rel_obj["priority"]
        romance_priority = romance_rel_obj["priority"]
        self.logger.debug(
            "comparing_priorities", friend_priority=friend_priority, romance_priority=romance_priority
        )
        primary_rel = friend_rel_obj if friend_priority >= romance_priority else romance_rel_obj
    elif friend_rel_obj:
        primary_rel = friend_rel_obj
    elif romance_rel_obj:
        primary_rel = romance_rel_obj

    self.logger.debug("primary_relationship_selected", primary_rel=primary_rel)

    # Start with base relationship attributes, which can be overridden
    if primary_rel:
        # These keys are mandatory in a valid relationship object.
        # Direct access enforces this contract.
        new_rel_type = primary_rel["type"]
        new_rel_level = primary_rel["level"]
        new_rel_style = primary_rel["style"]
        new_rel_threshold = primary_rel["threshold"]
    else:
        self.logger.warning(
            "Update failed, no relationship could be determined",
            original_type=original_rel_type,
            original_level=original_rel_level,
        )
        return

    # Apply override_config if it exists
    override_config = getattr(self.bot, "override_config", None)
    if override_config and isinstance(override_config, dict):
        self.logger.info("applying_override_config", override_config=override_config)
        for ovr_key, ovr_value in override_config.items():
            try:
                # Use direct access to enforce that the override configuration is valid.
                # This will raise a KeyError if a required key is missing.
                override_type = ovr_value["type"]
                override_level = ovr_value["override_level"]
                override_style = ovr_value["style"]
                set_flag_attr = ovr_value["set_flag"]
            except KeyError as e:
                self.logger.error(
                    "invalid_override_config",
                    missing_key=str(e),
                    override_key=ovr_key,
                    error="Skipping this malformed override rule.",
                )
                continue

            if not (set_flag_attr and hasattr(self, set_flag_attr) and getattr(self, set_flag_attr)):
                self.logger.warning(
                    "Override config flag attribute is missing or False", override_config=override_config
                )
                continue

            if override_type != new_rel_type:
                self.logger.debug(
                    "Skipping override because relationship type mismatch", override_config=override_config
                )
                continue  # Only check active flags relevant to the current relationship type

            if ovr_key == new_rel_level:
                self.logger.info(f"Applying override '{ovr_key}' because flag '{set_flag_attr}' is True.")
                new_rel_level = override_level
                new_rel_style = override_style
                # An override is a transient state, turn off the flag once the relationship progresses beyond it.
                # The flag is NOT turned off upon application. It's turned off in the next block if level is higher.

            # Second, check for flags that should be turned off because the relationship has progressed
            if ovr_key != new_rel_level:
                override_rel_obj = self._get_level_by_name(ovr_key, new_rel_type)
                if not override_rel_obj:
                    self.logger.warning("Could not find override level object for key", key=ovr_key)
                    continue
                override_threshold = override_rel_obj["threshold"]
                override_level_name = override_level
                if new_rel_threshold > override_threshold:
                    self.logger.info(
                        f"Setting flag '{set_flag_attr}' to False because current level "
                        f"'{new_rel_level}' is higher than override level '{override_level_name}'."
                    )
                    setattr(self, set_flag_attr, False)
                else:
                    self.logger.info(
                        f"Skipping flag '{set_flag_attr}' because current level "
                        f"'{new_rel_level}' is lower than override level '{override_level_name}'."
                    )

    # Update relationship attributes with the final, potentially overridden, values
    self.relationship_type = new_rel_type
    self.relationship_level = new_rel_level
    self.relationship_style = new_rel_style

    self.logger.info(
        "relationship_updated",
        bot_id=self.bot.entity_id,
        relationship_type=self.relationship_type,
        relationship_level=self.relationship_level,
        friend_level=self.friend_level,
        friend_buffer_status=self.friend_buffer_status,
        romance_level=self.romance_level,
        romance_buffer_status=self.romance_buffer_status,
    )


def format_emotions_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensures that the keys of the thresholds in emotions_config are integers.

    This function serves as a safeguard. Even if the data from the database
    is already correctly formatted, this function will ensure that any in-memory
    modifications or inconsistencies are handled before the config is used.
    """
    if not config or not isinstance(config, dict):
        return {}

    try:
        formatted_config = {}
        for emotion_type, details in config.items():
            if (
                isinstance(details, dict)
                and "thresholds" in details
                and isinstance(details.get("thresholds"), dict)
            ):
                # Create a deepcopy to avoid modifying the original dict in-place
                new_details = details.copy()
                new_details["thresholds"] = {int(k): v for k, v in details["thresholds"].items()}
                formatted_config[emotion_type] = new_details
            else:
                formatted_config[emotion_type] = details
        return formatted_config
    except (ValueError, TypeError) as e:
        self.logger.warning("failed_to_format_emotions_config", config=config, error=str(e))
        return config  # Return original on error


def new_anger_emotion(
    self, anger_emotion_score: int, friend_score_change: int, romance_score_change: int
) -> None:
    """
    Creates a new anger emotion record.
    """
    try:
        if anger_emotion_score <= 0:
            self.logger.warning("invalid_anger_score", score=anger_emotion_score)
            return

        self.logger.debug("processing_new_anger_emotion", score=anger_emotion_score)

        # Get bot configuration values
        emotions_config = self._format_emotions_config(getattr(self.bot, "emotions_config"))
        friend_score_neg_k = getattr(self.bot, "friend_score_neg_k")

        # Get anger configs
        anger_config = emotions_config.get(EmotionType.ANGER.value)
        if not anger_config or "thresholds" not in anger_config:
            self.logger.error("anger_config_or_thresholds_missing", config=emotions_config)
            return

        anger_thresholds = anger_config.get("thresholds")
        anger_calc_rules = self.emotion_calculation_rules.get(EmotionType.ANGER.value)

        # Determine anger level based on current score
        emotion_level = 0
        # Sort levels by threshold to find the correct level
        sorted_threshold = sorted(anger_thresholds.items(), key=lambda item: item[1])
        for level, threshold in sorted_threshold:
            if anger_emotion_score >= threshold:
                emotion_level = int(level)
        if emotion_level == 0:
            self.logger.info("anger_level_too_low", score=anger_emotion_score)
            return

        self.logger.debug("determined_anger_level", level=emotion_level, score=anger_emotion_score)

        # Get thresholds for each level directly from the config
        lv1_threshold = anger_thresholds.get(1)
        lv2_threshold = anger_thresholds.get(2)
        lv3_threshold = anger_thresholds.get(3)

        # Set decay ratio based on anger level using config
        decay_ratios = anger_calc_rules.get("decay_ratios")
        decay_ratio = decay_ratios.get(emotion_level)

        # Calculate score deltas based on tiered system
        friend_score_delta = 0
        romance_score_delta = 0

        # Get score multipliers from config
        score_multipliers = anger_calc_rules.get("score_multipliers")

        # Calculate score deltas based on anger level
        if emotion_level >= 1:
            lv1_score_mult = score_multipliers.get(1)
            stage_score = min(anger_emotion_score - lv1_threshold + 1, lv2_threshold - lv1_threshold)
            friend_score_delta -= -friend_score_change * stage_score * lv1_score_mult
            romance_score_delta -= -romance_score_change * stage_score * lv1_score_mult
            self.logger.debug(
                "level1_score_calculation",
                stage_score=stage_score,
                friend_delta=friend_score_delta,
                romance_delta=romance_score_delta,
            )
        if emotion_level >= 2:
            lv2_score_mult = score_multipliers.get(2)
            stage_score = min(anger_emotion_score - lv2_threshold + 1, lv3_threshold - lv2_threshold)
            friend_score_delta -= round(self.friend_score * stage_score * lv2_score_mult / 100)
            romance_score_delta -= round(self.romance_score * stage_score * lv2_score_mult / 100)
            self.logger.debug(
                "level2_score_calculation",
                stage_score=stage_score,
                friend_delta=friend_score_delta,
                romance_delta=romance_score_delta,
            )
        if emotion_level == 3:
            lv3_score_mult = score_multipliers.get(3)
            stage_score = min(anger_emotion_score - lv3_threshold + 1, 13 - lv3_threshold)
            friend_score_delta -= round(self.friend_score * 2 ** (stage_score - 1) * lv3_score_mult / 100)
            romance_score_delta -= round(self.romance_score * 2 ** (stage_score - 1) * lv3_score_mult / 100)
            self.logger.debug(
                "level3_score_calculation",
                stage_score=stage_score,
                friend_delta=friend_score_delta,
                romance_delta=romance_score_delta,
            )

        # Calculate duration based on anger level
        now = datetime.now(timezone.utc)
        end_time = now

        # Apply duration formula based on level using config duration multipliers
        # Get duration multipliers and random range from config
        duration_multipliers = anger_calc_rules.get("duration_multipliers")
        duration_random_range = anger_calc_rules.get("duration_random_range")
        duration_multiplier = duration_multipliers.get(emotion_level)

        # Calculate base duration in minutes
        base_minutes = round(stage_score * 120 / friend_score_neg_k * duration_multiplier)
        self.logger.debug(
            "base_duration_calculated", base_minutes=base_minutes, multiplier=duration_multiplier
        )

        # Apply random factor from config range
        random_factor = random.uniform(*duration_random_range)
        minutes = base_minutes * random_factor
        end_time = now + timedelta(minutes=minutes)
        self.logger.debug("final_duration_calculated", minutes=minutes, random_factor=random_factor)

        # New anger emotion
        new_anger_emotion = {
            EmotionType.ANGER.value: {
                "emotion_score": anger_emotion_score,
                "original_emotion_score": anger_emotion_score,
                "emotion_level": emotion_level,
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

        # Clear existing anger emotion while preserving other emotions
        if EmotionType.ANGER.value in self.emotions:
            self.logger.debug(
                "clearing_existing_anger_emotion",
                previous_score=self.emotions[EmotionType.ANGER.value].get("emotion_score", 0),
            )
            del self.emotions[EmotionType.ANGER.value]

        # Update local emotions data with new anger emotion
        self.emotions.update(new_anger_emotion)
        self.logger.debug("emotions_updated_with_new_anger")

        # Sleep probability
        sleep_probability = anger_emotion_score * emotion_level / 3
        random_value = random.random()
        if random_value < sleep_probability:
            self.is_awake = False
            self.logger.info(
                "bot_sleep_triggered", probability=sleep_probability, random_value=random_value
            )

        self.logger.info(
            "new_anger_emotion_created",
            emotion_score=anger_emotion_score,
            emotion_level=emotion_level,
            friend_delta=friend_score_delta,
            romance_delta=romance_score_delta,
            duration_minutes=minutes,
            end_time=end_time.isoformat(),
            decay_ratio=decay_ratio,
        )

    except Exception as e:
        self.logger.error("error_creating_anger_emotion", error=str(e), exc_info=True)


def process_emotions_and_score(self, response_result: dict) -> None:
    """Process score changes and emotions from response content and update scores accordingly.

    This method focuses exclusively on processing anger emotions:
    1. Extracts anger score from response content
    2. Calculates appropriate emotion level based on configured thresholds
    3. Computes score deltas using a tiered calculation system
    4. Sets emotion duration based on anger level
    5. Updates or creates anger emotion records
    """
    # Check if emotions data exists in the response
    if "emotions" not in response_result:
        self.logger.warning("no_emotions_data_in_response")
        if "friend_score" not in response_result or "romance_score" not in response_result:
            self.logger.warning("no_score_data_in_response")
            return

    emotions_data = response_result.get("emotions", {})
    friend_score_change = response_result.get("friend_score", 0)
    romance_score_change = response_result.get("romance_score", 0)

    # Friend score and romance score only decrease in negative mode
    negative_mode = False
    for emotion, emotion_score in emotions_data.items():
        try:
            if emotion_score < 0 or emotion_score > 12:
                self.logger.warning("invalid_emotion_score", emotion=emotion, score=emotion_score)
                continue

            if emotion == EmotionType.MOVED.value:
                if friend_score_change > 0:
                    self.friend_score += friend_score_change * emotion_score
                if romance_score_change > 0:
                    self.romance_score += romance_score_change * emotion_score
                self.logger.info("moved_emotion_processed", emotion_score=emotion_score)

            elif emotion == EmotionType.ANGER.value:
                negative_mode = True
                # Check if we already have an anger emotion
                existing_anger = self.emotions.get(EmotionType.ANGER.value, {})
                ex_angr_sc = existing_anger.get("emotion_score", 0)
                ex_orig_angr_sc = existing_anger.get("original_emotion_score", 0)
                ex_is_ended = existing_anger.get("is_ended", False)

                # ==== Create a new anger emotion ====
                # If no anger emotion or the existing anger is ended or new anger score more than existing
                if not existing_anger or ex_angr_sc == 0 or ex_is_ended or ex_orig_angr_sc < emotion_score:
                    self.logger.debug("creating_new_anger_emotion", score=emotion_score)
                    # Get relationship scores from response
                    self._new_anger_emotion(emotion_score, friend_score_change, romance_score_change)
                else:
                    self.logger.debug("updating_existing_anger_emotion", score=emotion_score)
                    # Prepare updated emotion data
                    updated_emotion: Dict[str, Any] = {}

                    # ==== Update the existing anger emotion ====
                    ratio = emotion_score / ex_orig_angr_sc
                    ex_orig_fnd_sc_delta = existing_anger.get("original_friend_score_delta", 0)
                    ex_orig_rom_sc_delta = existing_anger.get("original_romance_score_delta", 0)

                    # Update score deltas proportionally and round to the nearest integer
                    friend_score_delta = round(ex_orig_fnd_sc_delta * ratio)
                    romance_score_delta = round(ex_orig_rom_sc_delta * ratio)

                    # # No ideal way to adjust end time, so just keep the original end time
                    # # Adjust end time if ratio exceeds decay ratio
                    # ex_orig_end_time = self._ensure_datetime(existing_anger.get("original_end_time", ""))
                    # ex_start_time = self._ensure_datetime(existing_anger.get("start_time", ""))

                    # decay_ratio = existing_anger.get("decay_ratio", 0)

                    # if ex_orig_end_time and ex_start_time and ratio > decay_ratio:
                    #     # Calculate new duration as a fraction of original
                    #     original_duration = (ex_orig_end_time - ex_start_time).total_seconds()
                    #     new_duration = original_duration * (decay_ratio - 1 + ratio)
                    #     end_time = ex_start_time + timedelta(seconds=new_duration)

                    now = datetime.now(timezone.utc)

                    updated_emotion = {
                        EmotionType.ANGER.value: {
                            **existing_anger,
                            "emotion_score": emotion_score,
                            "friend_score_delta": friend_score_delta,
                            "romance_score_delta": romance_score_delta,
                            # "end_time": end_time.isoformat(),
                            "update_time": now.isoformat(),
                        }
                    }

                    # Update local emotions data
                    self.emotions.update(updated_emotion)

            if self.emotions:
                self.logger.info(
                    "emotion_processed", emotion=emotion, score=emotion_score, emotions=self.emotions
                )
            else:
                self.logger.warning(
                    "no_emotions_data_in_response",
                    emotion=emotion,
                    score=emotion_score,
                    emotions=self.emotions,
                )
        except Exception as e:
            self.logger.error("error_processing_emotion", emotion=emotion, error=str(e), exc_info=True)

    if negative_mode:
        friend_score_change = min(friend_score_change, 0)
        romance_score_change = min(romance_score_change, 0)

    self.friend_score += friend_score_change
    self.romance_score += romance_score_change
