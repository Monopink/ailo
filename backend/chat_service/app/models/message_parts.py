import asyncio
from typing import Optional
from datetime import datetime

from enums import MessageType, TypingStatus
from event_bus import event_bus, EventTypes


async def send_message(
    self, content: Optional[str] = "", message_type: str = MessageType.CHAT.name
) -> None:
    try:
        message = {
            "from_entity": str(self.bot.entity_id),
            "to_entity": str(self.bot.user_entity_id),
            "content": str(content),
            "message_type": message_type,
            "message_service": self.message_service,
            "message_time": datetime.now().isoformat(),
        }
        self.logger.info(
            "sending_message",
            message_type=message_type,
            has_content=bool(content),
            from_entity=self.bot.entity_id,
            to_entity=self.bot.user_entity_id,
        )
        self.last_message_type = None  # To Calculate waiting time
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        self.logger.error("message_send_error", message_type=message_type, error=str(e), exc_info=True)


async def send_message_queue(self, message_type_key: str):
    """Helper function to send all messages from a specific queue."""
    i = 0
    while True:
        content_to_process = None
        # Use a lock to safely get the next message to process
        async with self.typing_queue_lock:
            if i >= len(self.typing_queue[message_type_key]):
                self.logger.debug(f"No more messages to send for {message_type_key}")
                break  # Exit loop if we've processed all messages
            item = self.typing_queue[message_type_key][i]
            if item["status"] == TypingStatus.PENDING.value:
                content_to_process = item["content"]

        if content_to_process:
            # Send typing indicator and wait for the duration of typing.
            # This part is outside the lock to avoid holding it during sleep.
            asyncio.create_task(self._send_message(message_type=MessageType.TYPING.name))
            typing_secs = len(str(content_to_process)) * self.typing_speed
            self.logger.info(f"Typing for {typing_secs:.2f} seconds for a message in '{message_type_key}'.")
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
                self.logger.info(f"Sent message from '{message_type_key}'.")
            else:
                self.logger.info(
                    f"Sending cancelled for message in '{message_type_key}' as it was modified during typing."
                )
        i += 1


async def process_typing_queue(self, wait_secs: float):
    """
    Sends queued messages. First sends all reply_messages, then waits for a
    specified duration, and finally sends all prepared_messages.
    Args:
        wait_secs: The time to wait between sending reply messages and prepared messages.
    """
    try:
        # Send reply messages
        self.logger.info("Starting to send 'reply_messages'.")
        await self._send_message_queue("reply_messages")

        # Wait for the specified time if there are prepared messages
        async with self.typing_queue_lock:
            has_prepared = bool(self.typing_queue["prepared_messages"])

        if has_prepared:
            self.logger.info(f"Waiting for {wait_secs:.2f} seconds before sending prepared messages.")
            await asyncio.sleep(wait_secs)

            # Send prepared messages
            self.logger.info("Starting to send 'prepared_messages'.")
            await self._send_message_queue("prepared_messages")
        else:
            self.logger.info("No prepared messages to send. Skipping wait.")

    except asyncio.CancelledError:
        self.logger.info("`process_typing_queue` task was cancelled during execution.")
        raise  # Re-raise to allow the caller (_process_reply) to handle it.
    except Exception as e:
        self.logger.error("Error in process_typing_queue", error=str(e), exc_info=True)


async def handle_interrupted_reply(self) -> None:
    """
    Handles the cleanup of the typing queue when a reply task is interrupted.
    This function moves unsent reply messages to `unsent_message` and clears
    pending prepared messages. This must be called before the old reply_task is cancelled.
    """
    async with self.typing_queue_lock:
        self.logger.info("Handling interrupted reply task. Cleaning up typing queue.")

        # --- Handle reply_messages ---
        unsent_reply_messages = [
            msg["content"]
            for msg in self.typing_queue["reply_messages"]
            if msg["status"] == TypingStatus.PENDING.value
        ]
        # Keep only messages that were already sent
        self.typing_queue["reply_messages"] = [
            msg for msg in self.typing_queue["reply_messages"] if msg["status"] == TypingStatus.SENT.value
        ]

        # --- Handle prepared_messages ---
        # All pending prepared messages are discarded as the context has changed.
        self.typing_queue["prepared_messages"].clear()

        # --- Save to self.unsent_message ---
        if unsent_reply_messages:
            self.unsent_message = self.message_tag.join(unsent_reply_messages)
            self.logger.info(f"Moved unsent reply messages to self.unsent_message: '{self.unsent_message}'")
