import asyncio
from typing import Optional
from datetime import datetime, timezone

from enums import MessageType, TypingStatus
from services.message.message import send_message
from ..protocols import ModelAiloLike


class MessageMixin:
    """Mixin class for handling message related functionality.

    This mixin provides methods for sending messages, handling typing indicators,
    and managing message queues. It expects to be mixed into a class that implements
    ModelAiloProtocol.
    """

    async def _send_message(
        self: ModelAiloLike, content: Optional[str] = "", message_type: MessageType = MessageType.CHAT
    ) -> None:
        try:
            await send_message(
                from_entity=str(self.bot.entity_id),
                to_entity=str(self.bot.user_entity_id),
                message_type=str(message_type.code),  # Use numeric code as string
                message_service=self.message_service,
                content=str(content),
                message_time=datetime.now(timezone.utc).isoformat(),
            )

            self.logger.info(
                "sending_message",
                message_type=message_type.name,
                has_content=bool(content),
                from_entity=self.bot.entity_id,
                to_entity=self.bot.user_entity_id,
            )

        except Exception as e:
            self.logger.error(
                "message_send_error", message_type=message_type.name, error=str(e), exc_info=True
            )

    async def _send_message_queue(self: ModelAiloLike, message_type_key: str):
        """Helper function to send all messages from a specific queue."""
        i = 0
        while True:
            content_to_process = None
            # Use a lock to safely get the next message to process
            async with self.typing_queue_lock:
                if i >= len(self.typing_queue[message_type_key]):
                    self.logger.debug("no_more_messages_to_send", queue_name=message_type_key)
                    break  # Exit loop if we've processed all messages
                item = self.typing_queue[message_type_key][i]
                if item["status"] == TypingStatus.PENDING.value:
                    content_to_process = item["content"]

            if content_to_process:
                # Send typing indicator and wait for the duration of typing.
                # This part is outside the lock to avoid holding it during sleep.
                asyncio.create_task(self._send_message(message_type=MessageType.TYPING))
                typing_secs = len(str(content_to_process)) * self.typing_speed
                self.logger.info(
                    "typing_for_message",
                    duration_sec=f"{typing_secs:.2f}",
                    queue_name=message_type_key,
                    content_preview=str(content_to_process)[:50],
                )
                await asyncio.sleep(typing_secs)

                # Re-acquire lock to atomically check status and send message
                message_was_sent = False
                async with self.typing_queue_lock:
                    # We need to check again if the message is still valid to be sent.
                    # It might have been cancelled during the typing sleep.
                    if i < len(self.typing_queue[message_type_key]):
                        item = self.typing_queue[message_type_key][i]
                        if (
                            item["content"] == content_to_process
                            and item["status"] == TypingStatus.PENDING.value
                        ):
                            item["status"] = TypingStatus.SENT.value
                            message_was_sent = True

                if message_was_sent:
                    await self._send_message(content=content_to_process)
                    self.logger.info(
                        "message_sent_from_queue",
                        queue_name=message_type_key,
                        content_preview=str(content_to_process)[:50],
                    )
                else:
                    self.logger.info(
                        "message_sending_cancelled_during_typing",
                        queue_name=message_type_key,
                        content_preview=str(content_to_process)[:50],
                    )
            i += 1

    async def _process_typing_queue(self: ModelAiloLike, wait_secs: float):
        """
        Sends queued messages. First sends all reply_messages, then waits for a
        specified duration, and finally sends all prepared_messages.
        Args:
            wait_secs: The time to wait between sending reply messages and prepared messages.
        """
        try:
            # Send reply messages
            self.logger.info("processing_reply_messages_queue")
            await self._send_message_queue("reply_messages")

            # Wait for the specified time if there are prepared messages
            async with self.typing_queue_lock:
                has_prepared = bool(self.typing_queue["prepared_messages"])

            if has_prepared:
                self.logger.info("waiting_before_prepared_messages", wait_sec=f"{wait_secs:.2f}")
                await asyncio.sleep(wait_secs)

                # Send prepared messages
                self.logger.info("processing_prepared_messages_queue")
                await self._send_message_queue("prepared_messages")
            else:
                self.logger.info("no_prepared_messages_skipping_wait")

        except asyncio.CancelledError:
            self.logger.info("process_typing_queue_cancelled")
            raise  # Re-raise to allow the caller (_process_reply) to handle it.
        except Exception as e:
            self.logger.error("process_typing_queue_failed", error=str(e), exc_info=True)

    async def _handle_interrupted_reply(self: ModelAiloLike) -> None:
        """
        Handles the cleanup of the typing queue when a reply task is interrupted.
        This function moves unsent reply messages to `unsent_message` and clears
        pending prepared messages. This must be called before the old reply_task is cancelled.
        """
        async with self.typing_queue_lock:
            self.logger.info("handling_interrupted_reply")

            # --- Handle reply_messages ---
            unsent_reply_messages = [
                msg["content"]
                for msg in self.typing_queue["reply_messages"]
                if msg["status"] == TypingStatus.PENDING.value
            ]
            # Keep only messages that were already sent
            self.typing_queue["reply_messages"] = [
                msg
                for msg in self.typing_queue["reply_messages"]
                if msg["status"] == TypingStatus.SENT.value
            ]

            # --- Handle prepared_messages ---
            # All pending prepared messages are discarded as the context has changed.
            self.typing_queue["prepared_messages"].clear()

            # --- Save to self.unsent_message ---
            if unsent_reply_messages:
                self.unsent_message = self.message_tag.join(unsent_reply_messages)
                self.logger.info("unsent_messages_saved", unsent_message=self.unsent_message)
