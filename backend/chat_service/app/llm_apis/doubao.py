import copy
import json
from typing import Dict, Any, Optional
from volcenginesdkarkruntime import Ark
from .base import BaseLLM
from ..utils.logging import get_logger

logger = get_logger(__name__)


class Doubao(BaseLLM):
    def __init__(self, api_key: str, model_id: str, base_url: Optional[str] = None):
        """
        Initialize Doubao API client
        Args:
            api_key: API key
            model_id: Model ID
            base_url: Base URL for API, optional
        """
        super().__init__()
        self.model_id = model_id
        self.base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        self.client = Ark(base_url=self.base_url, api_key=api_key)
        # Only use encryption during API calls, not affecting storage
        self.api_headers = {"x-is-encrypted": "true"}

    async def generate_response(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate response, ensure content is decrypted before storage"""
        logger.info("generating_response", context=context, kwargs=kwargs)
        try:
            messages = context.get("messages", [])
            if not messages:
                logger.warning("empty_messages_list")
                raise ValueError("Messages list is empty")

            # Create deep copy of messages for API call
            messages_for_api = copy.deepcopy(messages)

            # Construct API parameters
            api_params = {
                "model": self.model_id,
                "messages": messages_for_api,
                "extra_headers": self.api_headers,
                **kwargs,  # Dynamically add all other parameters
            }

            # Use API call
            completion = self.client.chat.completions.create(**api_params)

            # Ensure content is a JSON string before returning
            content_from_sdk = completion.choices[0].message.content
            if isinstance(content_from_sdk, dict):
                content_as_string = json.dumps(content_from_sdk, ensure_ascii=False)
            else:
                content_as_string = str(content_from_sdk)

            # Ensure decrypted content for storage
            logger.info("response_generated_successfully")
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content_as_string,
                        }
                    }
                ]
            }

        except Exception as e:
            logger.error("doubao_api_error", error=str(e), exc_info=True)
            raise

    async def validate_response(self, response: Dict) -> tuple[bool, Optional[str]]:
        logger.info("validating_response", response=response)
        try:
            if not isinstance(response, dict):
                logger.warning("invalid_response_type")
                return False, "Response is not a dictionary"

            if "choices" not in response:
                logger.warning("missing_choices_field")
                return False, "Response missing 'choices' field"

            choices = response["choices"]
            if not choices or not isinstance(choices, list):
                logger.warning("invalid_choices_list")
                return False, "Invalid or empty choices list"

            first_choice = choices[0]
            if "message" not in first_choice and "delta" not in first_choice:
                logger.warning("missing_message_and_delta_fields")
                return False, "Choice missing both 'message' and 'delta' fields"

            logger.info("response_validation_successful")
            return True, None

        except Exception as e:
            logger.error("validation_error", error=str(e), exc_info=True)
            return False, f"Validation error: {str(e)}"
