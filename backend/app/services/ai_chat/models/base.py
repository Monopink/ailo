from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Awaitable


class BaseModel(ABC):
    """Base model class"""

    def __init__(
        self,
        bot: Any,
        message_service: str,
        cleanup_callback: Callable[[str], Awaitable[None]],
    ):
        """
        Initialize the model
        Args:
            bot: Bot instance containing basic bot information
            message_service: Message service type
            cleanup_callback: Cleanup callback function that takes a string parameter (bot.entity_id) and returns an awaitable
        """
        self.bot = bot
        self.message_service = message_service
        self.cleanup_callback = cleanup_callback

    @abstractmethod
    async def receive_message(self, message: Dict[str, Any]) -> None:
        """
        Entry method for receiving messages

        Args:
            message: Message dictionary containing the following fields:
                - from_entity: str, sender ID
                - to_entity: str, receiver ID
                - content: str, message content
                - message_type: str, message type
                - message_service: str, message service type
                - message_time: str, message timestamp
        """
        pass
