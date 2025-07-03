from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseLLM(ABC):
    def __init__(self):
        self.model_id: Optional[str] = None

    @abstractmethod
    async def generate_response(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Generate response
        Args:
            context: Context dictionary containing message history, bot information, etc.
                {
                    "messages": List[Dict],  # Message history
                }
            **kwargs: Other parameters passed to the API
        Returns:
            Optional[Dict]: Response message
        """
        pass

    @abstractmethod
    async def validate_response(self, response: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate if the response conforms to the standard LLM response structure
        Args:
            response: LLM response content
        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        pass
