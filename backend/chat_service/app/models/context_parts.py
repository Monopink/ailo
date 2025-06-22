import json

try:
    from zhdate import ZhDate
except ImportError:
    print("zhdate is not installed. Please install it using 'pip install zhdate'.")
    exit(1)
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .context_strategy import ContextComponents, create_context, TaskDefinition
from enums import TaskType


def convert_timestamp(self, timestamp: str | None = None) -> str:
    """Convert UTC timestamp to time string in specified timezone
    Args:
        timestamp: UTC timestamp in ISO format (e.g. '2025-02-01T07:17:33.564Z'), if None, use current time
    Returns:
        Converted time string (e.g. '2025-02-01 07:17:35')
    """
    try:
        # Get timezone object
        timezone_obj = ZoneInfo(self.bot.timezone)

        if timestamp is None:
            # Use current UTC time
            utc_time = datetime.now(timezone.utc)
        else:
            # Parse UTC timestamp
            utc_time = datetime.strptime(timestamp.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z")

        # Convert to target timezone
        local_time = utc_time.astimezone(timezone_obj)
        # Format output using the timestamp format constant
        return local_time.strftime(self.timestamp_format)
    except ValueError as e:
        self.logger.error(f"ValueError in _convert_timestamp: {str(e)}")
        raise
    except Exception as e:
        self.logger.error(f"Unexpected error in _convert_timestamp: {str(e)}")
        raise


def create_fingerprint(self, text: str) -> str:
    """Creates a lightweight fingerprint for a text message."""
    if not text:
        return "0::"
    text_str = str(text)
    return f"{len(text_str)}:{text_str[:5]}:{text_str[-5:]}"


def create_instant_context(self) -> str:
    """Create instant context containing current time, basic status info and lunar calendar info
    Returns:
        str: Formatted instant context string
    """
    try:
        # Get current time in bot's timezone using _convert_timestamp
        current_time = self._convert_timestamp()

        # Parse current time string to datetime object using the timestamp format constant
        dt_current = datetime.strptime(current_time, self.timestamp_format)
        weekday_str = [
            "星期一",
            "星期二",
            "星期三",
            "星期四",
            "星期五",
            "星期六",
            "星期日",
        ][dt_current.weekday()]

        # Determine time period based on hour
        hour = int(current_time.split()[1].split(":")[0])
        if 0 <= hour < 6:
            time_period = "凌晨"
        elif 6 <= hour < 9:
            time_period = "早上"
        elif 9 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 14:
            time_period = "中午"
        elif 14 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 24:
            time_period = "晚上"
        else:
            self.logger.warning(f"Unknown time period for bot {self.bot.id}")
            time_period = ""

        # Get lunar calendar info using zhdate library
        lunar_info = ""
        try:
            lunar_info = f"农历：{ZhDate.from_datetime(dt_current).chinese()}"
        except Exception as e:
            self.logger.error(f"Error getting lunar calendar info: {str(e)}", exc_info=True)

        # Build instant context
        instant_context = (
            f"现在是{current_time}，{time_period}，{weekday_str}，"
            f"{lunar_info}\n"
            f"你在{self.bot.city_name if hasattr(self.bot, 'city_name') else '中国'}。"
        )

        if self.unsent_message:
            instant_context += f"[之前未发送消息]{self.unsent_message}"

        # 消息发送时间、年龄、用户名

        self.logger.info(f"Created instant context with time: {instant_context}")
        return instant_context

    except Exception as e:
        self.logger.error(f"Error creating instant context: {str(e)}", exc_info=True)
        return ""


def refresh_system_context(self) -> None:
    """Refresh system context

    Trims context, decides on summarization, then creates new system context
    and updates the current context strategy object.
    """
    try:
        # 1. Remove old, unimportant context first.
        self._remove_expire_context()

        # Helper to calculate total character count of context messages.
        def get_context_char_count():
            return sum(len(str(msg.get("content", ""))) for msg in self.context.get("messages", []))

        # 2. Check context length (character count) and decide on summarizing or trimming.
        if get_context_char_count() > self.context_limit:
            should_summarize = False
            if self.last_chat_time:
                # Ensure last_chat_time is timezone-aware.
                last_chat_time_aware = self._ensure_datetime(self.last_chat_time)
                now_aware = datetime.now(ZoneInfo(self.bot.timezone))

                time_diff_hours = (now_aware - last_chat_time_aware).total_seconds() / 3600

                # Check if it passed 4am since last chat.
                passed_4am = (now_aware.date() > last_chat_time_aware.date()) or (
                    now_aware.date() == last_chat_time_aware.date()
                    and now_aware.hour >= self.summary_time_point
                    and last_chat_time_aware.hour < self.summary_time_point
                )

                if time_diff_hours > self.min_summary_hours and passed_4am:
                    should_summarize = True

            if should_summarize:
                self.need_summary = True
                self.logger.info(
                    f"Context character count limit exceeded, setting need_summary to True for bot {self.bot.id}"
                )
            else:
                self.need_summary = False
                self.logger.info(
                    f"Context character count limit exceeded, but summarization conditions not met. "
                    f"Removing oldest messages until within limit for bot {self.bot.id}"
                )
                # Trim context by removing oldest messages until within limit.
                while get_context_char_count() > self.context_limit:
                    # Safeguard: stop if only system message is left.
                    if len(self.context.get("messages", [])) <= 1:
                        self.logger.warning(
                            f"Context still exceeds limit after trimming, but only system message is left for bot {self.bot.id}."
                        )
                        break
                    self._remove_oldest_context()
        else:
            self.need_summary = False

        # 3. Get instant context.
        self.instant_context = self._create_instant_context()

        # Create ContextComponents instance
        components = ContextComponents()

        # Set attributes
        components.info = self.bot.info
        components.memory = self.memory
        components.style = self.relationship_style
        components.instant_context = self.instant_context
        components.message_tag = self.message_tag
        components.include_summary = self.need_summary
        components.attack_content_replacement = self.attack_content_replacement

        # Pass current emotion data
        components.emotions = getattr(self, "emotions", {})

        # Create context strategy
        system_prompt, strategy = create_context(
            relationship_type=self.relationship_type,
            relationship_level=self.relationship_level,
            components=components,
            include_summary=self.need_summary,
            include_thought=not self.initial_message,
            memory_limit=self.memory_limit,
            include_extra_info=self.need_extra_info,
        )

        # Update current strategy object
        self.context_strategy_instance = strategy
        self.logger.info("Updated context strategy instance")

        new_system_context = {"role": "system", "content": system_prompt}

        # Update system message in context
        if "messages" in self.context and self.context["messages"]:
            self.context["messages"][0] = new_system_context
        else:
            self.context["messages"] = [new_system_context]

    except Exception as e:
        self.logger.error(f"Error refreshing system context: {str(e)}", exc_info=True)
        raise


def varify_context(self) -> None:
    """Verify context structure and initialize if needed"""
    try:
        is_valid = (
            isinstance(self.context, dict)
            and "messages" in self.context
            and isinstance(self.context["messages"], list)
            and self.context["messages"]
            and all(
                isinstance(msg, dict) and "role" in msg and "content" in msg
                for msg in self.context["messages"]
            )
        )

        if not is_valid:
            self.logger.warning(
                f"Invalid context structure detected for bot {self.bot.id}, initializing new context"
            )
            self.context = {"messages": []}
            self._refresh_system_context()

        self.logger.info(f"Context structure verified for bot {self.bot.id}")
    except Exception as e:
        self.logger.error(f"Error verifying context for bot {self.bot.id}: {str(e)}", exc_info=True)
        # Initialize context on error
        self.context = {"messages": []}
        # self._refresh_system_context()


def append_context(self, role: str, context_content: str) -> None:
    """Append or merge context messages

    Args:
        role: Message role ('system', 'user', or 'assistant')
        context_content: Message content
        timestamp: Message timestamp
    """
    try:
        # Construct new message
        new_message = {"role": role, "content": context_content}

        # Get last message
        last_message = self.context["messages"][-1]

        # Check if roles match
        if last_message["role"] == role:
            # Merge message content
            merged_content = f"{last_message['content']}\n{context_content}"
            last_message["content"] = merged_content
            self.logger.info(f"Merged message {merged_content} with same role for bot {self.bot.id}")
        else:
            # Add new message
            self.context["messages"].append(new_message)

            # Generate current timestamp for metadata
            current_timestamp = self._convert_timestamp()

            if not current_timestamp:
                self.logger.warning(
                    f"Could not generate timestamp for user content for bot {self.bot.id}: {context_content[:50]}"
                )
                current_timestamp = "N/A"

            user_metadata = {
                "timestamp": current_timestamp,
                "role": role,
                "fingerprint": self._create_fingerprint(context_content),
            }
            self.context_metadata.append(user_metadata)
            self.logger.info("Appended user context and metadata.")

        # self.logger.debug(f"Current context: {self.context}")

    except Exception as e:
        self.logger.error(f"Error appending context for bot {self.bot.id}: {str(e)}", exc_info=True)
        # Ensure context structure is intact on error
        if not self.context or "messages" not in self.context:
            self._varify_context()
            # self._append_context(role, context_content) # prevent infinite loop
            self.logger.error(f"Reset context structure for bot {self.bot.id} after error")


def append_response_to_context(self, llm_task_result: dict) -> None:
    """
    Processes an LLM response: appends assistant message to context, updates
    the previous user's metadata, and adds new metadata for the assistant.
    """
    try:
        # 1. Prepare the content for the assistant's message in the context
        content_value = llm_task_result.get(TaskDefinition.get_response_key(TaskType.REPLY_CONTENT), "")
        prepared_content_value = llm_task_result.get(
            TaskDefinition.get_response_key(TaskType.PREPARED_CONTENT), ""
        )
        # assistant_timestamp = self._convert_timestamp()

        # Build message with optional emotion and note tags
        # Example: [emotions]anger:5, happy:3
        emotions_part = ""
        emotions_data = llm_task_result.get(TaskDefinition.get_response_key(TaskType.EMOTION_SCORING))
        if emotions_data and isinstance(emotions_data, dict):
            # Add emotions part only if it's not just "none:0"
            if not (len(emotions_data) == 1 and "none" in emotions_data):
                emotions_str = ", ".join([f"{k}:{v}" for k, v in emotions_data.items()])
                if emotions_str:
                    emotions_part = f"[emotions]{emotions_str}"

        # Example: [note]对方开始询问地域信息...
        note_part = ""
        note_data = llm_task_result.get(TaskDefinition.get_response_key(TaskType.CONVERSATION_NOTE))
        if note_data and isinstance(note_data, str):
            note_part = f"[note]{note_data}"

        # Combine all parts for the savable content
        # Example: [2025-06-21...]\nHi[emotions]anger:1[note]...
        # saveable_content = f"[{assistant_timestamp}]\n{content_value}"
        saveable_content = content_value
        if prepared_content_value:
            saveable_content += self.message_tag + prepared_content_value
        if emotions_part:
            saveable_content += emotions_part
        if note_part:
            saveable_content += note_part

        assistant_message = {"role": "assistant", "content": saveable_content}
        self.context["messages"].append(assistant_message)

        # 2. Update the previous user's metadata
        if self.context_metadata and self.context_metadata[-1].get("role") == "user":
            user_meta = self.context_metadata[-1]
            user_meta["is_attack"] = llm_task_result.get(
                TaskDefinition.get_response_key(TaskType.IS_ATTACK), False
            )
            user_meta["is_important"] = llm_task_result.get(
                TaskDefinition.get_response_key(TaskType.IS_IMPORTANT), False
            )
        else:
            self.logger.warning(
                "Could not find a preceding user metadata entry to update for bot %s",
                self.bot.id,
            )

        # 3. Add new metadata for the assistant's response, maintaining order
        # This order should align with the TaskDefinition in context_strategy.py
        assistant_timestamp = self._convert_timestamp()
        assistant_metadata = {
            "timestamp": assistant_timestamp,
            "role": "assistant",
            "fingerprint": self._create_fingerprint(saveable_content),
        }
        # PRE_RESPONSE_THINKING
        thought_key = TaskDefinition.get_response_key(TaskType.PRE_THINKING)
        if thought_key in llm_task_result:
            assistant_metadata[thought_key] = llm_task_result.get(thought_key)
        # EMOTION_SCORING
        emotion_key = TaskDefinition.get_response_key(TaskType.EMOTION_SCORING)
        assistant_metadata[emotion_key] = llm_task_result.get(emotion_key, {})
        # FRIEND_SCORING
        friend_score_key = TaskDefinition.get_response_key(TaskType.FRIEND_SCORING)
        assistant_metadata[friend_score_key] = llm_task_result.get(friend_score_key, 0)
        # ROMANCE_SCORING
        romance_score_key = TaskDefinition.get_response_key(TaskType.ROMANCE_SCORING)
        assistant_metadata[romance_score_key] = llm_task_result.get(romance_score_key, 0)
        # CONVERSATION_NOTE
        note_key = TaskDefinition.get_response_key(TaskType.CONVERSATION_NOTE)
        if note_key in llm_task_result and llm_task_result[note_key]:
            assistant_metadata[note_key] = llm_task_result.get(note_key)
        # IS_IMPORTANT
        important_key = TaskDefinition.get_response_key(TaskType.IS_IMPORTANT)
        assistant_metadata[important_key] = llm_task_result.get(important_key, False)
        # PREPARED_CONTENT
        next_content_key = TaskDefinition.get_response_key(TaskType.PREPARED_CONTENT)
        if next_content_key in llm_task_result and llm_task_result[next_content_key]:
            assistant_metadata[next_content_key] = llm_task_result.get(next_content_key)
        # IS_BLOCK
        block_key = TaskDefinition.get_response_key(TaskType.IS_BLOCK)
        if block_key in llm_task_result:
            assistant_metadata[block_key] = llm_task_result.get(block_key)

        self.context_metadata.append(assistant_metadata)
        self.logger.info("Appended assistant response to context and metadata.")

    except json.JSONDecodeError as e:
        self.logger.error(
            f"Failed to decode LLM response JSON for bot {self.bot.id}: {e}",
            exc_info=True,
        )
    except Exception as e:
        self.logger.error(
            f"Error appending response to context for bot {self.bot.id}: {e}",
            exc_info=True,
        )


def process_attack_context(self) -> None:
    """Process attack context

    Checks if the last context message is from the user. If it is, preserves only
    the timestamp and removes all other content, then logs a warning with the
    full content as a potential attack message.
    """
    try:
        # Check if context exists and has messages
        if not self.context or "messages" not in self.context or not self.context["messages"]:
            self.logger.warning(
                f"No context messages found for bot {self.bot.id} when processing attack context"
            )
            return

        # Get the last message in the context (user message) and its metadata
        last_message = self.context["messages"][-1]

        # Check if the last message is from the user
        if last_message["role"] != "user":
            self.logger.warning(
                f"Last message for bot {self.bot.id} is not from user, cannot process attack context"
            )
            return

        if not self.context_metadata:
            self.logger.warning(f"Metadata is empty for bot {self.bot.id}, cannot process attack context.")
            return

        last_metadata = self.context_metadata[-1]

        # Verify fingerprint before proceeding
        expected_fingerprint = last_metadata.get("fingerprint")
        actual_fingerprint = self._create_fingerprint(last_message.get("content", ""))

        if expected_fingerprint != actual_fingerprint:
            self.logger.warning(
                f"Fingerprint mismatch for bot {self.bot.id} during attack processing. "
                f"Expected: {expected_fingerprint}, Got: {actual_fingerprint}. "
                f"Content: {last_message.get('content', '')[:50]}..."
            )
            return

        # Get the full content for logging
        full_content = last_message["content"]

        # Log the full content as a warning (potential attack message)
        self.logger.warning(f"Detected attack message from user for bot {self.bot.id}: {full_content}")

        # Just use the replacement message directly. The short timestamp `[HH:MM]`
        # is part of the content and will be replaced along with it.
        sanitized_content = self.attack_content_replacement

        # Update the message content and its fingerprint in metadata
        last_message["content"] = sanitized_content
        last_metadata["fingerprint"] = self._create_fingerprint(sanitized_content)
        self.logger.info(f"Sanitized attack context and updated fingerprint for bot {self.bot.id}")

    except Exception as e:
        self.logger.error(
            f"Error processing attack context for bot {self.bot.id}: {str(e)}",
            exc_info=True,
        )


def remove_oldest_context(self) -> None:
    """
    Removes the oldest non-system message from the context after verifying its fingerprint.
    """
    try:
        # Context must have at least a system message and one other message.
        if len(self.context.get("messages", [])) <= 1:
            self.logger.info(f"No message to remove or only system message remains for bot {self.bot.id}")
            return

        # We assume system message is at index 0 and has no metadata.
        # So, the first conversational message is at index 1.
        # And its metadata is at index 0 of context_metadata.
        if not self.context_metadata:
            self.logger.warning(
                f"Context has messages but metadata is empty for bot {self.bot.id}. Cannot remove oldest message."
            )
            return

        message_to_remove = self.context["messages"][1]
        metadata_to_check = self.context_metadata[0]

        # Verify fingerprint
        expected_fingerprint = metadata_to_check.get("fingerprint")
        actual_fingerprint = self._create_fingerprint(message_to_remove.get("content", ""))

        if expected_fingerprint != actual_fingerprint:
            self.logger.warning(
                f"Fingerprint mismatch for bot {self.bot.id}. "
                f"Cannot remove oldest context. "
                f"Expected: {expected_fingerprint}, Got: {actual_fingerprint}. "
                f"Content: {message_to_remove.get('content', '')[:50]}..."
            )
            return

        # Fingerprints match, proceed with removal
        self.context["messages"].pop(1)
        self.context_metadata.pop(0)
        self.logger.info(f"Removed oldest context message and its metadata for bot {self.bot.id}")

    except IndexError:
        self.logger.error(
            f"IndexError while trying to remove oldest context for bot {self.bot.id}. Context or metadata might be malformed.",
            exc_info=True,
        )
    except Exception as e:
        self.logger.error(f"Error removing oldest context for bot {self.bot.id}: {str(e)}", exc_info=True)


def remove_expire_context(self, include_important: bool = False) -> None:
    """Removes expired messages from the context based on age and count thresholds."""
    try:
        # 1. Pre-condition checks: Both count and age must exceed thresholds.
        num_conversational_messages = len(self.context.get("messages", [])) - 1
        if num_conversational_messages < self.context_expire_num:
            return

        if not self.context_metadata:
            return

        timestamp_str = self.context_metadata[0].get("timestamp")
        if not timestamp_str or timestamp_str == "N/A":
            return

        is_old_enough = False
        try:
            message_time = datetime.strptime(timestamp_str, self.timestamp_format)
            message_time = message_time.replace(tzinfo=ZoneInfo(self.bot.timezone))
            now_aware = datetime.now(ZoneInfo(self.bot.timezone))
            is_old_enough = (now_aware - message_time).total_seconds() > self.context_expire_hours * 3600
        except (ValueError, TypeError):
            self.logger.error(
                f"Could not parse timestamp for pre-check in remove_expire_context for bot {self.bot.id}"
            )
            return

        if not is_old_enough:
            return

        self.logger.info(f"Conditions met, starting expired context removal for bot {self.bot.id}.")
        # 2. Loop and remove messages that are old enough.
        metadata_index = 0
        while metadata_index < len(self.context_metadata):
            message_index = metadata_index + 1
            if message_index >= len(self.context.get("messages", [])):
                break

            metadata = self.context_metadata[metadata_index]
            is_important = metadata.get("is_important", True)

            # Decide whether to delete this message.
            if include_important or not is_important:
                # Verify fingerprint before removing.
                message_to_remove = self.context["messages"][message_index]
                expected_fingerprint = metadata.get("fingerprint")
                actual_fingerprint = self._create_fingerprint(message_to_remove.get("content", ""))

                if expected_fingerprint == actual_fingerprint:
                    self.context["messages"].pop(message_index)
                    self.context_metadata.pop(metadata_index)
                    self.logger.info(
                        f"Removed expired message for bot {self.bot.id} with timestamp {metadata.get('timestamp')}"
                    )
                    # Don't increment index, as the list has shifted.
                    continue
                else:
                    self.logger.warning(
                        f"Fingerprint mismatch in remove_expire_context for bot {self.bot.id}. Stopping removal."
                    )
                    break  # Stop on mismatch
            else:
                # Old but is_important, and we are not including them. Skip.
                metadata_index += 1
    except Exception as e:
        self.logger.error(
            f"Error in remove_expire_context for bot {self.bot.id}: {e}",
            exc_info=True,
        )


def summary_to_memory(self, llm_task_result: dict) -> None:
    """Processes the summary from the LLM response and updates memory."""
    try:
        summary_key = TaskDefinition.get_response_key(TaskType.CONVERSATION_SUMMARY)
        summary = llm_task_result.get(summary_key)

        if summary is None:
            if self.need_summary:
                self.logger.warning(
                    f"need_summary for bot {self.bot.id} was True, but LLM response did not contain a 'summary'."
                )
            return

        if len(summary) > self.memory_limit:
            summary = summary[: self.memory_limit]
            self.logger.info(f"Summary for bot {self.bot.id} was truncated to memory_limit.")

        self.memory = summary
        self.logger.info(f"Updated memory for bot {self.bot.id} with new summary.")

        # After updating memory, remove all expired contexts
        self._remove_expire_context(include_important=True)
    except Exception as e:
        self.logger.error(f"Error in summary_to_memory for bot {self.bot.id}: {e}", exc_info=True)
