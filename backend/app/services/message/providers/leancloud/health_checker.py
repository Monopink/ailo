"""
LeanCloud Message Service Health Checker

Class-based organization with stateless design for LeanCloud message service health checking.
Provides comprehensive health checking for LeanCloud message service components.
"""

import requests
from typing import Dict, Any, Tuple

from utils.logging import get_logger
from core.config import settings
from core.database import SessionLocal
from .conversation_manager import get_leancloud_conversation_id

logger = get_logger(__name__)


class LeanCloudMessageServiceHealthChecker:
    """
    Stateless health checker for LeanCloud message service.

    Provides health checking functionality with class-based organization
    but maintains stateless design principles.
    """

    async def check_leancloud_message_service_health(self) -> Dict[str, Any]:
        """
        Check LeanCloud message service health.

        Returns:
            dict: Health status response in standard format
        """
        try:
            logger.info("performing_leancloud_message_service_health_check")

            # Check LeanCloud API connectivity
            api_healthy, api_error = await self._check_leancloud_api_connectivity()

            # Check conversation ID availability
            conversation_healthy, conversation_error = (
                await self._check_leancloud_conversation_id_availability()
            )

            # Determine overall service health
            overall_healthy = api_healthy and conversation_healthy
            service_status = "healthy" if overall_healthy else "unhealthy"

            # Build response according to design document format
            response = {
                "leancloud_message_service": service_status,
                "leancloud_api": "healthy" if api_healthy else "unhealthy",
                "leancloud_conversation_id": "healthy" if conversation_healthy else "unhealthy",
                "details": {},
            }

            # Add error details if any
            if api_error:
                response["details"]["api_error"] = api_error
            if conversation_error:
                response["details"]["conversation_error"] = conversation_error

            logger.info(
                "leancloud_message_service_health_check_completed",
                service_status=service_status,
                api_healthy=api_healthy,
                conversation_healthy=conversation_healthy,
            )

            return response

        except Exception as e:
            logger.error("leancloud_message_service_health_check_failed", error=str(e), exc_info=True)
            return {
                "leancloud_message_service": "error",
                "leancloud_api": "error",
                "leancloud_conversation_id": "error",
                "details": {"error": str(e)},
            }

    async def _check_leancloud_api_connectivity(self) -> Tuple[bool, str]:
        """
        Check LeanCloud API connectivity.

        Returns:
            tuple: (is_healthy, error_message)
        """
        try:
            # Validate required settings
            app_id = settings.LEANCLOUD_APP_ID
            master_key = settings.LEANCLOUD_MASTER_KEY
            base_url = settings.LEANCLOUD_BASE_URL

            if not app_id or not master_key or not base_url:
                return False, "LeanCloud credentials not configured"

            # Test API access by querying service conversations
            url = f"{base_url}/1.2/rtm/service-conversations"
            headers = {
                "X-LC-Id": app_id,
                "X-LC-Key": f"{master_key},master",
                "Content-Type": "application/json",
            }

            # Make test request with timeout
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                logger.debug("leancloud_api_connectivity_check_passed")
                return True, ""
            else:
                error_msg = f"LeanCloud API returned status {response.status_code}"
                logger.warning("leancloud_api_connectivity_check_failed", status_code=response.status_code)
                return False, error_msg

        except requests.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error("leancloud_api_connectivity_network_error", error=str(e))
            return False, error_msg
        except Exception as e:
            error_msg = f"API connectivity check failed: {str(e)}"
            logger.error("leancloud_api_connectivity_check_error", error=str(e), exc_info=True)
            return False, error_msg

    async def _check_leancloud_conversation_id_availability(self) -> Tuple[bool, str]:
        """
        Check LeanCloud conversation ID availability.

        Returns:
            tuple: (is_healthy, error_message)
        """
        try:
            # Get conversation ID from database using new conversation_manager
            async with SessionLocal() as db:
                conversation_id = await get_leancloud_conversation_id(db)

            if not conversation_id:
                return False, "LeanCloud conversation ID not configured"

            # Validate conversation exists in LeanCloud
            is_valid = await self._validate_conversation_exists(conversation_id)

            if is_valid:
                logger.debug("leancloud_conversation_id_check_passed", conversation_id=conversation_id)
                return True, ""
            else:
                error_msg = f"Conversation {conversation_id} not found in LeanCloud"
                logger.warning("leancloud_conversation_id_check_failed", conversation_id=conversation_id)
                return False, error_msg

        except ValueError as e:
            error_msg = f"Conversation ID configuration error: {str(e)}"
            logger.error("leancloud_conversation_id_config_error", error=str(e))
            return False, error_msg
        except Exception as e:
            error_msg = f"Conversation ID check failed: {str(e)}"
            logger.error("leancloud_conversation_id_check_error", error=str(e), exc_info=True)
            return False, error_msg

    async def _validate_conversation_exists(self, conversation_id: str) -> bool:
        """
        Validate that conversation exists in LeanCloud.

        Args:
            conversation_id: The conversation ID to validate

        Returns:
            bool: True if conversation exists, False otherwise
        """
        try:
            url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"
            headers = {
                "X-LC-Id": settings.LEANCLOUD_APP_ID,
                "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
                "Content-Type": "application/json",
            }

            # Query for specific conversation ID
            params = {"where": f'{{"objectId": "{conversation_id}"}}'}

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                response_data = response.json()
                results = response_data.get("results", [])

                # Check if conversation was found
                for result in results:
                    if isinstance(result, dict) and result.get("objectId") == conversation_id:
                        return True

                return False
            else:
                logger.error(
                    "leancloud_conversation_validation_api_error",
                    status_code=response.status_code,
                    conversation_id=conversation_id,
                )
                return False

        except Exception as e:
            logger.error(
                "leancloud_conversation_validation_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return False


# Create instance
health_checker = LeanCloudMessageServiceHealthChecker()
