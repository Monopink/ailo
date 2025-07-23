import json
from typing import Any, Dict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    from zhdate import ZhDate
except ImportError:
    print("zhdate is not installed. Please install it using 'pip install zhdate'.")
    exit(1)
from enums import TaskType

from ..context_strategy import ContextComponents, create_context, TaskDefinition
from ..protocols import ModelAiloLike


class ContextMixin:
    def _convert_timestamp(self: ModelAiloLike, timestamp: str | None = None) -> str:
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
            self.logger.error("timestamp_conversion_value_error", error=str(e))
            raise
        except Exception as e:
            self.logger.error("timestamp_conversion_unexpected_error", error=str(e))
            raise

    def _create_fingerprint(self: ModelAiloLike, text: str) -> str:
        """Creates a lightweight fingerprint for a text message."""
        if not text:
            return "0::"
        text_str = str(text)
        return f"{len(text_str)}:{text_str[:5]}:{text_str[-5:]}"

    def _verify_single_metadata(self: ModelAiloLike, message: dict, metadata: dict) -> bool:
        """Verifies a single message against its metadata entry and logs on failure."""
        if not message or not metadata:
            self.logger.warning(
                "verify_single_metadata_failed_empty_input",
                message_exists=bool(message),
                metadata_exists=bool(metadata),
            )
            return False

        expected_role = message.get("role")
        actual_role = metadata.get("role")
        is_role_mismatch = actual_role != expected_role

        expected_fingerprint = self._create_fingerprint(message.get("content", ""))
        actual_fingerprint = metadata.get("fingerprint")
        is_fingerprint_mismatch = actual_fingerprint != expected_fingerprint

        is_mismatch = is_role_mismatch or is_fingerprint_mismatch
        if is_mismatch:
            self.logger.warning(
                "single_metadata_verification_failed",
                reason="Mismatch found between message and its metadata.",
                is_role_mismatch=is_role_mismatch,
                expected_role=expected_role,
                actual_role=actual_role,
                is_fingerprint_mismatch=is_fingerprint_mismatch,
                expected_fingerprint=expected_fingerprint,
                actual_fingerprint=actual_fingerprint,
                offending_metadata=metadata,
                message_content_preview=message.get("content", "")[:100],
            )

        return not is_mismatch

    def _create_repaired_metadata(self: ModelAiloLike, message: dict) -> dict:
        """Creates a new, repaired metadata entry for a given context message."""
        content = message.get("content", "")
        role = message.get("role")
        return {
            "role": role,
            "fingerprint": self._create_fingerprint(content),
            "timestamp": self._convert_timestamp(),
            "is_important": True,  # Assume importance when repairing
            "repaired": True,
        }

    def _verify_and_repair_metadata(self: ModelAiloLike) -> None:
        """
        Verifies context and metadata consistency by iterating through them.
        - If a mismatch is found, it rebuilds metadata from that point.
        - If metadata is longer than messages, it truncates the excess.
        - If messages are longer than metadata, it appends the missing metadata.
        This is a non-destructive self-healing mechanism.
        """

        try:
            messages = self.context.get("messages", [])
            if not messages:
                if self.context_metadata:
                    self.logger.warning(
                        "context_is_empty_but_metadata_exists",
                        reason="Context messages are empty, clearing metadata.",
                    )
                    self.context_metadata.clear()
                return

            conversational_messages = messages[1:]
            num_convo_messages = len(conversational_messages)
            num_metadata_entries = len(self.context_metadata)

            # Iterate through the common length of messages and metadata
            common_len = min(num_convo_messages, num_metadata_entries)
            for i in range(common_len):
                message = conversational_messages[i]
                metadata = self.context_metadata[i]
                if not self._verify_single_metadata(message, metadata):
                    self.logger.warning(
                        "context_metadata_mismatch_found_rebuilding",
                        index=i,
                        reason="Rebuilding metadata from this point due to mismatch.",
                    )
                    # Keep the consistent part and rebuild the rest
                    consistent_part = self.context_metadata[:i]
                    rebuilt_part = [
                        self._create_repaired_metadata(msg) for msg in conversational_messages[i:]
                    ]
                    self.context_metadata = consistent_part + rebuilt_part
                    self.logger.info(
                        f"Successfully rebuilt context metadata from index {i}.",
                        rebuilt_count=len(rebuilt_part),
                    )
                    return  # Repair is done

            # If the loop completes, the common part is consistent. Now handle tails.
            if num_convo_messages > num_metadata_entries:
                # Messages are longer, so append missing metadata
                self.logger.warning(
                    "context_longer_than_metadata_and_appending",
                    message_count=num_convo_messages,
                    metadata_count=num_metadata_entries,
                    reason="Appending missing metadata for extra messages.",
                )
                rebuilt_tail = [
                    self._create_repaired_metadata(msg)
                    for msg in conversational_messages[num_metadata_entries:]
                ]
                self.context_metadata.extend(rebuilt_tail)
                self.logger.info(
                    "Successfully appended missing metadata.", appended_count=len(rebuilt_tail)
                )

            elif num_metadata_entries > num_convo_messages:
                # Metadata is longer, so truncate the excess
                self.logger.warning(
                    "metadata_longer_than_context_and_truncating",
                    message_count=num_convo_messages,
                    metadata_count=num_metadata_entries,
                    reason="Truncating excess metadata entries.",
                )
                self.context_metadata = self.context_metadata[:num_convo_messages]
                self.logger.info("Successfully truncated excess metadata.")

            self.logger.info("Context and metadata consistency verified successfully.")

        except Exception as e:
            self.logger.critical(
                "unexpected_error_in_context_verification",
                error=str(e),
                exc_info=True,
                reason="An unexpected error occurred. Context was NOT cleared, but may be inconsistent.",
                context=self.context,
                metadata=self.context_metadata,
            )

    def _create_instant_context(self: ModelAiloLike) -> str:
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
            elif 9 <= hour < 11:
                time_period = "上午"
            elif 11 <= hour < 14:
                time_period = "中午"
            elif 14 <= hour < 18:
                time_period = "下午"
            elif 18 <= hour < 24:
                time_period = "晚上"
            else:
                self.logger.warning("unknown_time_period", hour=hour)
                time_period = ""

            # Get lunar calendar info using zhdate library
            lunar_info = ""
            try:
                lunar_info = f"农历：{ZhDate.from_datetime(dt_current).chinese()}"
            except Exception as e:
                self.logger.error("lunar_info_generation_failed", error=str(e), exc_info=True)

            # Build instant context
            instant_context = (
                f"现在是{current_time} {time_period}，{weekday_str}，"
                f"{lunar_info}，"
                f"你在{self.bot.city_name if hasattr(self.bot, 'city_name') else '中国'}。"
            )

            if self.unsent_message:
                instant_context += f"\n[之前未发送消息]{self.unsent_message}"

            # Add user profile information if available
            if hasattr(self, "user_profile") and self.user_profile:
                user_info = self._format_user_profile_for_context(self.user_profile)
                if user_info:
                    instant_context += f"\n用户资料：{user_info}"

            # Add profile change information if available
            if hasattr(self, "profile_changes") and self.profile_changes:
                instant_context += f"\n{self.profile_changes}"

            self.logger.info("instant_context_created", context=instant_context)
            return instant_context

        except Exception as e:
            self.logger.error("create_instant_context_failed", error=str(e), exc_info=True)
            return ""

    def _refresh_system_context(self: ModelAiloLike) -> None:
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
                    if last_chat_time_aware:
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
                    self.logger.info("context_limit_exceeded_will_summarize")
                else:
                    self.need_summary = False
                    self.logger.warning(
                        "context_limit_exceeded_will_trim",
                        context_size=get_context_char_count(),
                        context_limit=self.context_limit,
                    )
                    # Trim context by removing oldest messages until within limit, with a safety break.
                    max_trims = len(self.context.get("messages", []))  # Safety break
                    trims_done = 0
                    while get_context_char_count() > self.context_limit:
                        # Safeguard 1: Stop if only the system message is left.
                        if len(self.context.get("messages", [])) <= 1:
                            self.logger.warning(
                                "context_trimming_stopped_only_system_message_left",
                                context_size=get_context_char_count(),
                                context_limit=self.context_limit,
                            )
                            break
                        # Safeguard 2: Prevent infinite loops.
                        if trims_done >= max_trims:
                            self.logger.error(
                                "context_trimming_stopped_max_retries_reached",
                                context_size=get_context_char_count(),
                                context_limit=self.context_limit,
                                max_trims=max_trims,
                                reason="Stopped trimming to prevent potential infinite loop.",
                            )
                            break

                        # Remove oldest context and check result
                        was_removed = self._remove_oldest_context()
                        if not was_removed:
                            self.logger.error(
                                "context_trimming_stopped_removal_failed",
                                reason="Stopped trimming because remove_oldest_context failed to remove an entry.",
                                context_size=get_context_char_count(),
                                context_limit=self.context_limit,
                            )
                            break  # Stop if removal fails

                        trims_done += 1
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
            self.logger.info("context_strategy_updated")

            new_system_context = {"role": "system", "content": system_prompt}

            # Update system message in context
            if "messages" in self.context and self.context["messages"]:
                self.context["messages"][0] = new_system_context
            else:
                self.context["messages"] = [new_system_context]

        except Exception as e:
            self.logger.error("refresh_system_context_failed", error=str(e), exc_info=True)
            raise

    def _varify_context(self: ModelAiloLike) -> None:
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
                self.logger.warning("invalid_context_structure_initializing")
                self.context = {"messages": []}
                self._refresh_system_context()

            self.logger.info("context_structure_verified")
        except Exception as e:
            self.logger.error("verify_context_failed", error=str(e), exc_info=True)
            # Initialize context on error
            self.context = {"messages": []}
            # self._refresh_system_context()

    def _append_context(self: ModelAiloLike, role: str, context_content: str) -> None:
        """Append or merge context messages

        Args:
            role: Message role ('system', 'user', or 'assistant')
            context_content: Message content
        """
        try:
            last_message = self.context["messages"][-1] if self.context.get("messages") else None
            last_metadata = self.context_metadata[-1] if self.context_metadata else None

            # 1. If the role is the same as the last message, merge them.
            if last_message and last_metadata and last_message["role"] == role:
                # First, verify the state BEFORE the merge to catch pre-existing issues.
                if not self._verify_single_metadata(last_message, last_metadata):
                    self.logger.warning(
                        "pre_merge_metadata_inconsistent_repairing",
                        reason="Metadata was inconsistent before merging. Repairing it for the original content.",
                    )
                    # Repair the metadata for the *original* last_message before proceeding
                    last_metadata = self._create_repaired_metadata(last_message)
                    self.context_metadata[-1] = last_metadata

                # Now merge content and update fingerprint
                merged_content = f"{last_message['content']}\n{context_content}"
                last_message["content"] = merged_content
                last_metadata["fingerprint"] = self._create_fingerprint(merged_content)
                self.logger.info("context_merged_and_fingerprint_updated")
                return

            # 2. If roles are different, append a new message and its metadata.
            # Construct new message and append
            new_message = {"role": role, "content": context_content}
            self.context["messages"].append(new_message)

            # Generate new metadata and append
            current_timestamp = self._convert_timestamp()
            if not current_timestamp:
                self.logger.warning(
                    "timestamp_generation_failed_for_new_content", content_preview=context_content[:50]
                )
                current_timestamp = "N/A"

            new_metadata = {
                "timestamp": current_timestamp,
                "role": role,
                "fingerprint": self._create_fingerprint(context_content),
            }
            self.context_metadata.append(new_metadata)
            self.logger.info("new_context_appended_with_metadata")

        except Exception as e:
            self.logger.error(
                "append_context_failed",
                error=str(e),
                role=role,
                context_content=context_content,
                exc_info=True,
            )
            # Ensure context structure is intact on error
            if not self.context or "messages" not in self.context:
                self._varify_context()
                self.logger.error("context_structure_reset_after_error")

    def _append_response_to_context(self: ModelAiloLike, llm_task_result: dict) -> None:
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
                    "preceding_user_metadata_not_found",
                    last_message_role=(
                        self.context["messages"][-1].get("role") if self.context.get("messages") else "N/A"
                    ),
                    llm_task_result=llm_task_result,
                )

            # 3. Add new metadata for the assistant's response, maintaining order
            # This order should align with the TaskDefinition in context_strategy.py
            assistant_timestamp = self._convert_timestamp()
            assistant_metadata: Dict[str, Any] = {
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
            self.logger.info("assistant_response_appended_to_context")

        except json.JSONDecodeError as e:
            self.logger.error(
                "llm_response_json_decode_failed",
                error=str(e),
                llm_task_result=llm_task_result,
                exc_info=True,
            )
        except Exception as e:
            self.logger.error(
                "append_response_to_context_failed",
                error=str(e),
                llm_task_result=llm_task_result,
                exc_info=True,
            )

    def _process_attack_context(self: ModelAiloLike) -> None:
        """Process attack context

        Checks if the last context message is from the user. If it is, preserves only
        the timestamp and removes all other content, then logs a warning with the
        full content as a potential attack message.
        """
        try:
            # Check if context exists and has messages
            if not self.context or "messages" not in self.context or not self.context["messages"]:
                self.logger.warning("process_attack_context_no_messages")
                return

            # Get the last message in the context (user message) and its metadata
            last_message = self.context["messages"][-1]

            # Check if the last message is from the user
            if last_message["role"] != "user":
                self.logger.warning(
                    "process_attack_context_last_message_not_user",
                    last_role=last_message.get("role"),
                )
                return

            if not self.context_metadata:
                self.logger.warning("process_attack_context_metadata_empty")
                return

            last_metadata = self.context_metadata[-1]

            # Verify fingerprint before proceeding
            try:
                if not self._verify_single_metadata(last_message, last_metadata):
                    self.logger.warning(
                        "process_attack_context_fingerprint_mismatch",
                        reason="Fingerprint mismatch for potential attack. Content will not be sanitized.",
                        content_preview=last_message.get("content", "")[:50],
                    )
                    return

                # Get the full content for logging
                full_content = last_message["content"]

                # Log the full content as a warning (potential attack message)
                self.logger.warning("attack_message_detected", full_content=full_content)

                # Just use the replacement message directly. The short timestamp `[HH:MM]`
                # is part of the content and will be replaced along with it.
                sanitized_content = self.attack_content_replacement

                # Update the message content and its fingerprint in metadata
                last_message["content"] = sanitized_content
                last_metadata["fingerprint"] = self._create_fingerprint(sanitized_content)
                self.logger.info("attack_context_sanitized")
            except KeyError as e:
                self.logger.error(
                    "process_attack_context_failed_missing_key",
                    missing_key=str(e),
                    reason="A message or metadata entry is missing a required key.",
                    last_message=last_message,
                    last_metadata=last_metadata,
                    exc_info=True,
                )

        except Exception as e:
            self.logger.error(
                "process_attack_context_failed",
                error=str(e),
                last_message=self.context.get("messages", [])[-1] if self.context.get("messages") else None,
                exc_info=True,
            )

    def _remove_oldest_context(self: ModelAiloLike) -> bool:
        """
        Removes the oldest non-system message from the context after verifying its fingerprint.
        Returns:
            bool: True if a message was successfully removed, False otherwise.
        """
        try:
            # Context must have at least a system message and one other message.
            if len(self.context.get("messages", [])) <= 1:
                self.logger.info("remove_oldest_context_nothing_to_remove")
                return False

            # We assume system message is at index 0 and has no metadata.
            # So, the first conversational message is at index 1.
            # And its metadata is at index 0 of context_metadata.
            if not self.context_metadata:
                self.logger.warning("remove_oldest_context_metadata_empty")
                return False

            message_to_remove = self.context["messages"][1]
            metadata_to_check = self.context_metadata[0]

            # Verify fingerprint
            if not self._verify_single_metadata(message_to_remove, metadata_to_check):
                # SAFETY MEASURE: Log a severe warning about the mismatch, but proceed with
                # removal to prevent infinite loops in the calling function. This is a
                # self-healing action to remove corrupted/inconsistent data.
                self.logger.error(
                    "fingerprint_mismatch_forcing_removal",
                    reason="Forcing removal of oldest context entry to prevent infinite loops.",
                )
                # Fall through to the removal logic even on mismatch.

            # Fingerprints match or mismatch (in which case we force removal), proceed.
            removed_message = self.context["messages"].pop(1)
            removed_metadata = self.context_metadata.pop(0)
            self.logger.info(
                "oldest_context_removed",
                removed_message=removed_message,
                removed_metadata=removed_metadata,
            )
            return True

        except IndexError:
            self.logger.error(
                "remove_oldest_context_index_error",
                exc_info=True,
                reason="Context or metadata might be malformed.",
                context=self.context,
                metadata=self.context_metadata,
            )
            return False
        except Exception as e:
            self.logger.error("remove_oldest_context_failed", error=str(e), exc_info=True)
            return False

    def _remove_expire_context(self: ModelAiloLike, include_important: bool = False) -> None:
        """
        Removes expired messages from the context by iterating through each message.

        A message is removed if it meets all the following criteria:
        - The total number of conversational messages is greater than `self.context_expire_num`.
        - The message's timestamp is older than `self.context_expire_hours`.
        - The message is not marked as important, or `include_important` is True.

        The process stops as soon as it encounters a message that is not old enough,
        or when the message count drops to the configured limit.
        """
        try:
            self.logger.info("remove_expire_context_starting", include_important=include_important)

            metadata_index = 0
            now_utc = datetime.now(timezone.utc)
            bot_timezone = ZoneInfo(self.bot.timezone)

            # Use a while loop because we are modifying the list we are iterating over.
            while metadata_index < len(self.context_metadata):
                # --- Stop Condition 1: Check message count ---
                num_conversational_messages = len(self.context.get("messages", [])) - 1
                if num_conversational_messages <= self.context_expire_num:
                    self.logger.info(
                        "remove_expire_context_stopped_count_threshold_reached",
                        message_count=num_conversational_messages,
                        threshold=self.context_expire_num,
                    )
                    break

                # Get metadata for the current message
                try:
                    metadata = self.context_metadata[metadata_index]
                    timestamp_str = metadata.get("timestamp")
                except IndexError:
                    self.logger.error("remove_expire_context_index_error_metadata", index=metadata_index)
                    break  # Should not happen if loop condition is correct
                except KeyError:
                    self.logger.error(
                        "remove_expire_context_aborted_missing_timestamp",
                        reason="Metadata entry is missing 'timestamp' key.",
                        metadata=metadata,
                    )
                    metadata_index += 1
                    continue

                if not timestamp_str or timestamp_str == "N/A":
                    self.logger.warning(
                        "remove_expire_context_skipping_invalid_timestamp",
                        timestamp=timestamp_str,
                        index=metadata_index,
                    )
                    metadata_index += 1
                    continue

                # --- Stop Condition 2: Check message age ---
                try:
                    naive_message_time = datetime.strptime(timestamp_str, self.timestamp_format)
                    aware_message_time = naive_message_time.replace(tzinfo=bot_timezone)
                    time_difference_hours = (now_utc - aware_message_time).total_seconds() / 3600

                    if time_difference_hours < self.context_expire_hours:
                        self.logger.info(
                            "remove_expire_context_stopped_age_threshold_reached",
                            message_age_hours=time_difference_hours,
                            threshold_hours=self.context_expire_hours,
                            timestamp=timestamp_str,
                        )
                        break  # Stop processing since messages are ordered by time
                except (ValueError, TypeError) as e:
                    self.logger.error(
                        "remove_expire_context_timestamp_parse_error",
                        timestamp=timestamp_str,
                        error=str(e),
                    )
                    metadata_index += 1
                    continue

                # --- Removal Logic: Check importance ---
                is_important = metadata.get("is_important", True)  # Default to True to be safe
                if include_important or not is_important:
                    # Corresponds to conversational messages, which start at index 1
                    message_index = metadata_index + 1

                    try:
                        message_to_remove = self.context["messages"][message_index]
                    except IndexError:
                        self.logger.error("remove_expire_context_index_error_message", index=message_index)
                        break

                    # We can remove the message. Let's do a final fingerprint check.
                    if self._verify_single_metadata(message_to_remove, metadata):
                        removed_message = self.context["messages"].pop(message_index)
                        removed_metadata = self.context_metadata.pop(metadata_index)
                        self.logger.info(
                            "expired_message_removed",
                            removed_message=removed_message,
                            removed_metadata=removed_metadata,
                        )
                        # Do not increment metadata_index, as the list has shifted and the next item is now at the current index.
                        continue
                    else:
                        self.logger.warning(
                            "remove_expire_context_fingerprint_mismatch_stopping",
                            reason="Stopping removal of expired context to ensure data integrity.",
                        )
                        # On mismatch, we stop the whole process to be safe.
                        break
                else:
                    # Message is important and we are not including them, so we skip it.
                    metadata_index += 1

        except Exception as e:
            self.logger.error(
                "remove_expire_context_failed",
                error=str(e),
                include_important=include_important,
                context=self.context,
                metadata=self.context_metadata,
                exc_info=True,
            )

    def _summary_to_memory(self: ModelAiloLike, llm_task_result: dict) -> None:
        """Processes the summary from the LLM response and updates memory."""
        try:
            summary_key = TaskDefinition.get_response_key(TaskType.CONVERSATION_SUMMARY)
            summary = llm_task_result.get(summary_key)

            if summary is None:
                if self.need_summary:
                    self.logger.warning("summary_missing_in_llm_response", llm_task_result=llm_task_result)
                return

            if len(summary) > self.memory_limit:
                summary = summary[: self.memory_limit]
                self.logger.info("summary_truncated_to_memory_limit")

            self.memory = summary
            self.logger.info("memory_updated_with_summary")

            # After updating memory, remove all expired contexts
            self._remove_expire_context(include_important=True)
        except Exception as e:
            self.logger.error(
                "summary_to_memory_failed", error=str(e), llm_task_result=llm_task_result, exc_info=True
            )
