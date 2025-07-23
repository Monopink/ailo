"""
LeanCloud Conversation Health Checker Service

This service provides independent health checking for LeanCloud conversation IDs.
It maintains separation of concerns and does not couple with other modules.
No default values are provided - problems are exposed immediately.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime
import requests

from utils.logging import get_logger
from core.config import settings
from .conversation_logger import conversation_logger, conversation_metrics
from .config_manager import get_unified_conversation_id, is_conversation_configured

logger = get_logger(__name__)


class ConversationHealthStatus:
    """Health status enumeration using numeric values for security"""

    UNKNOWN = 0
    HEALTHY = 1
    UNHEALTHY = 2
    CRITICAL = 3


class LeanCloudHealthChecker:
    """
    Independent health checker for LeanCloud conversation IDs.

    This service:
    - Validates conversation ID existence and accessibility
    - Performs periodic health checks
    - Maintains health status without coupling to other services
    - Exposes problems immediately without fallbacks
    """

    def __init__(self):
        self._health_status = ConversationHealthStatus.UNKNOWN
        self._last_check_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._check_count = 0
        self._failure_count = 0
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

        # Configuration - no defaults, fail fast if not configured
        self._check_interval_seconds = self._get_check_interval()
        self._timeout_seconds = self._get_timeout()

    def _get_check_interval(self) -> int:
        """Get health check interval from environment, no default value"""
        interval = getattr(settings, "LEANCLOUD_HEALTH_CHECK_INTERVAL", None)
        if interval is None:
            raise ValueError("LEANCLOUD_HEALTH_CHECK_INTERVAL must be configured")
        return int(interval)

    def _get_timeout(self) -> int:
        """Get health check timeout from environment, no default value"""
        timeout = getattr(settings, "LEANCLOUD_HEALTH_CHECK_TIMEOUT", None)
        if timeout is None:
            raise ValueError("LEANCLOUD_HEALTH_CHECK_TIMEOUT must be configured")
        return int(timeout)

    async def start_health_monitoring(self) -> None:
        """Start periodic health monitoring"""
        if self._running:
            logger.warning("health_checker_already_running")
            return

        self._running = True
        self._check_task = asyncio.create_task(self._health_check_loop())
        logger.info("leancloud_health_monitoring_started", interval_seconds=self._check_interval_seconds)

    async def stop_health_monitoring(self) -> None:
        """Stop periodic health monitoring"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("leancloud_health_monitoring_stopped")

    async def _health_check_loop(self) -> None:
        """Main health check loop"""
        while self._running:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self._check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_loop_error", error=str(e), exc_info=True)
                await asyncio.sleep(self._check_interval_seconds)

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform a single health check of the conversation ID.

        Returns:
            Dict containing health check results
        """
        check_start_time = time.time()
        self._check_count += 1

        logger.debug("performing_conversation_health_check", check_number=self._check_count)

        conversation_logger.log_health_monitoring_status(
            is_monitoring=self._running,
            check_interval=self._check_interval_seconds,
            total_checks=self._check_count,
            failure_count=self._failure_count,
        )

        try:
            # Check if conversation ID is configured
            if not is_conversation_configured():
                self._update_health_status(
                    ConversationHealthStatus.CRITICAL, "Conversation ID not configured"
                )
                return self._get_health_report(check_start_time, False)

            # Get conversation ID
            try:
                conversation_id = get_unified_conversation_id()
            except ValueError as e:
                self._update_health_status(
                    ConversationHealthStatus.CRITICAL, f"Failed to get conversation ID: {str(e)}"
                )
                return self._get_health_report(check_start_time, False)

            # Validate conversation exists and is accessible
            is_healthy = await self._validate_conversation_accessibility(conversation_id)

            check_duration_ms = int((time.time() - check_start_time) * 1000)

            if is_healthy:
                self._update_health_status(ConversationHealthStatus.HEALTHY, None)

                conversation_logger.log_conversation_health_check(
                    conversation_id=conversation_id, is_healthy=True, check_duration_ms=check_duration_ms
                )
                conversation_metrics.record_health_check(True, check_duration_ms)

                logger.debug(
                    "conversation_health_check_passed",
                    conversation_id=conversation_id,
                    check_duration_ms=check_duration_ms,
                )
            else:
                self._failure_count += 1

                conversation_logger.log_conversation_health_check(
                    conversation_id=conversation_id,
                    is_healthy=False,
                    check_duration_ms=check_duration_ms,
                    error=self._last_error,
                )
                conversation_metrics.record_health_check(False, check_duration_ms)

                # Trigger auto-recovery for critical failures
                if self._health_status == ConversationHealthStatus.CRITICAL:
                    await self._trigger_auto_recovery(conversation_id, self._last_error or "Unknown error")

            return self._get_health_report(check_start_time, is_healthy)

        except Exception as e:
            self._failure_count += 1
            self._update_health_status(ConversationHealthStatus.UNHEALTHY, f"Health check failed: {str(e)}")
            logger.error(
                "conversation_health_check_failed",
                error=str(e),
                check_number=self._check_count,
                exc_info=True,
            )
            return self._get_health_report(check_start_time, False)

    async def _validate_conversation_accessibility(self, conversation_id: str) -> bool:
        """
        Validate that the conversation ID exists and is accessible via LeanCloud API.

        Args:
            conversation_id: The conversation ID to validate

        Returns:
            bool: True if conversation is accessible, False otherwise
        """
        try:
            # Use LeanCloud REST API to query service conversations and check if our ID exists
            # Note: There's no direct GET /service-conversations/{id} API, so we query the list
            url = f"{settings.LEANCLOUD_BASE_URL}/1.2/rtm/service-conversations"
            headers = {
                "X-LC-Id": settings.LEANCLOUD_APP_ID,
                "X-LC-Key": f"{settings.LEANCLOUD_MASTER_KEY},master",
                "Content-Type": "application/json",
            }

            # Query with where clause to find our specific conversation ID
            params = {"where": f'{{"objectId": "{conversation_id}"}}'}

            # Track API call performance
            api_start_time = time.time()

            # Use asyncio to run the synchronous request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, headers=headers, params=params, timeout=self._timeout_seconds),
            )

            api_duration_ms = int((time.time() - api_start_time) * 1000)

            # Log API call performance
            conversation_logger.log_api_call_performance(
                api_endpoint="/1.2/rtm/service-conversations",
                method="GET",
                status_code=response.status_code,
                duration_ms=api_duration_ms,
                conversation_id=conversation_id,
            )

            if response.status_code == 200:
                # Check if response has valid content
                try:
                    response_data = response.json()
                except ValueError as e:
                    # Invalid JSON response
                    conversation_metrics.record_api_call(False, api_duration_ms)
                    self._update_health_status(
                        ConversationHealthStatus.UNHEALTHY,
                        f"Invalid JSON response from LeanCloud API: {str(e)}",
                    )
                    logger.error(
                        "conversation_invalid_json_response",
                        conversation_id=conversation_id,
                        response_text=response.text,
                        error=str(e),
                    )
                    return False

                # Check if our conversation ID was found in the results
                if not self._is_conversation_found_in_results(response_data, conversation_id):
                    conversation_metrics.record_api_call(False, api_duration_ms)
                    return False

                # Conversation exists and is accessible
                conversation_metrics.record_api_call(True, api_duration_ms)

                # Get the conversation data from results for logging
                conversation_data = self._extract_conversation_from_results(response_data, conversation_id)
                logger.debug(
                    "conversation_accessibility_validated",
                    conversation_id=conversation_id,
                    conversation_name=conversation_data.get("name") if conversation_data else None,
                )
                return True
            elif response.status_code == 404:
                # Conversation does not exist - this is critical
                conversation_metrics.record_api_call(False, api_duration_ms)
                self._update_health_status(
                    ConversationHealthStatus.CRITICAL, f"Conversation {conversation_id} not found (404)"
                )
                logger.error(
                    "conversation_not_found",
                    conversation_id=conversation_id,
                    status_code=response.status_code,
                )
                return False
            else:
                # Other error
                conversation_metrics.record_api_call(False, api_duration_ms)
                self._update_health_status(
                    ConversationHealthStatus.UNHEALTHY, f"API returned status {response.status_code}"
                )
                logger.error(
                    "conversation_api_error",
                    conversation_id=conversation_id,
                    status_code=response.status_code,
                    response_text=response.text,
                )
                return False

        except requests.RequestException as e:
            self._update_health_status(ConversationHealthStatus.UNHEALTHY, f"Network error: {str(e)}")
            logger.error("conversation_network_error", conversation_id=conversation_id, error=str(e))
            return False
        except Exception as e:
            self._update_health_status(ConversationHealthStatus.UNHEALTHY, f"Validation error: {str(e)}")
            logger.error(
                "conversation_validation_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return False

    def _is_conversation_found_in_results(
        self, response_data: Dict[str, Any], conversation_id: str
    ) -> bool:
        """
        Check if our conversation ID is found in the LeanCloud query results.

        Args:
            response_data: JSON response from LeanCloud service-conversations query
            conversation_id: The conversation ID we're looking for

        Returns:
            bool: True if conversation is found, False otherwise
        """
        try:
            # LeanCloud query response format: {"results": [...]}
            if not isinstance(response_data, dict) or "results" not in response_data:
                self._update_health_status(
                    ConversationHealthStatus.UNHEALTHY,
                    "Invalid response format from LeanCloud API: missing 'results' field",
                )
                logger.error(
                    "conversation_invalid_response_format",
                    conversation_id=conversation_id,
                    response_data=response_data,
                )
                return False

            results = response_data["results"]
            if not isinstance(results, list):
                self._update_health_status(
                    ConversationHealthStatus.UNHEALTHY, "Invalid response format: 'results' is not a list"
                )
                logger.error(
                    "conversation_results_not_list",
                    conversation_id=conversation_id,
                    results_type=type(results).__name__,
                )
                return False

            # Check if results is empty (conversation not found)
            if len(results) == 0:
                self._update_health_status(
                    ConversationHealthStatus.CRITICAL,
                    f"Conversation {conversation_id} not found in service conversations",
                )
                logger.error(
                    "conversation_not_found_in_results",
                    conversation_id=conversation_id,
                    total_results=len(results),
                )
                return False

            # Check if we found exactly one result with matching objectId
            found_conversation = None
            for result in results:
                if isinstance(result, dict) and result.get("objectId") == conversation_id:
                    found_conversation = result
                    break

            if found_conversation is None:
                self._update_health_status(
                    ConversationHealthStatus.CRITICAL,
                    f"Conversation {conversation_id} not found in query results",
                )
                logger.error(
                    "conversation_id_not_in_results",
                    conversation_id=conversation_id,
                    results_count=len(results),
                )
                return False

            # Conversation found - validate it's a proper service conversation
            if not self._validate_service_conversation(found_conversation, conversation_id):
                return False

            return True

        except Exception as e:
            self._update_health_status(
                ConversationHealthStatus.UNHEALTHY, f"Error checking conversation in results: {str(e)}"
            )
            logger.error(
                "conversation_results_check_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return False

    def _extract_conversation_from_results(
        self, response_data: Dict[str, Any], conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract our conversation data from LeanCloud query results.

        Args:
            response_data: JSON response from LeanCloud service-conversations query
            conversation_id: The conversation ID we're looking for

        Returns:
            Dict containing conversation data, or None if not found
        """
        try:
            results = response_data.get("results", [])
            for result in results:
                if isinstance(result, dict) and result.get("objectId") == conversation_id:
                    return result
            return None
        except Exception as e:
            logger.error(
                "conversation_extraction_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return None

    def _validate_service_conversation(
        self, conversation_data: Dict[str, Any], conversation_id: str
    ) -> bool:
        """
        Validate that conversation data represents a valid service conversation.

        Args:
            conversation_data: Conversation data from LeanCloud API
            conversation_id: The conversation ID being validated

        Returns:
            bool: True if conversation is valid, False otherwise
        """
        try:
            # Check required fields for a service conversation
            required_fields = ["objectId", "createdAt"]
            for field in required_fields:
                if field not in conversation_data:
                    self._update_health_status(
                        ConversationHealthStatus.UNHEALTHY,
                        f"Service conversation {conversation_id} missing required field: {field}",
                    )
                    logger.error(
                        "conversation_missing_required_field",
                        conversation_id=conversation_id,
                        missing_field=field,
                        conversation_data=conversation_data,
                    )
                    return False

            # Verify objectId matches what we're looking for
            if conversation_data.get("objectId") != conversation_id:
                self._update_health_status(
                    ConversationHealthStatus.UNHEALTHY,
                    f"Conversation objectId mismatch: expected {conversation_id}, got {conversation_data.get('objectId')}",
                )
                logger.error(
                    "conversation_id_mismatch",
                    expected_id=conversation_id,
                    actual_id=conversation_data.get("objectId"),
                )
                return False

            return True

        except Exception as e:
            self._update_health_status(
                ConversationHealthStatus.UNHEALTHY, f"Error validating service conversation: {str(e)}"
            )
            logger.error(
                "conversation_validation_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def _trigger_auto_recovery(self, failed_conversation_id: str, error_reason: str) -> None:
        """
        Trigger automatic recovery for failed conversation ID.

        Args:
            failed_conversation_id: The conversation ID that failed
            error_reason: Reason for the failure
        """
        try:
            logger.info(
                "triggering_auto_recovery",
                failed_conversation_id=failed_conversation_id,
                error_reason=error_reason,
            )

            # Import recovery service to avoid circular imports
            from .auto_recovery import recovery_service

            # Attempt recovery in background (don't block health check)
            asyncio.create_task(recovery_service.attempt_recovery(failed_conversation_id, error_reason))

        except Exception as e:
            logger.error(
                "failed_to_trigger_auto_recovery",
                failed_conversation_id=failed_conversation_id,
                error=str(e),
                exc_info=True,
            )

    def _update_health_status(self, status: int, error_message: Optional[str]) -> None:
        """Update internal health status"""
        self._health_status = status
        self._last_check_time = datetime.now()
        self._last_error = error_message

        if error_message:
            logger.warning("conversation_health_status_changed", status=status, error=error_message)

    def _get_health_report(self, check_start_time: float, is_healthy: bool) -> Dict[str, Any]:
        """Generate health check report"""
        check_duration_ms = int((time.time() - check_start_time) * 1000)

        return {
            "status": self._health_status,
            "is_healthy": is_healthy,
            "last_check_time": self._last_check_time.isoformat() if self._last_check_time else None,
            "last_error": self._last_error,
            "check_count": self._check_count,
            "failure_count": self._failure_count,
            "check_duration_ms": check_duration_ms,
            "is_monitoring": self._running,
        }

    def get_current_health_status(self) -> Dict[str, Any]:
        """Get current health status without performing a new check"""
        return {
            "status": self._health_status,
            "last_check_time": self._last_check_time.isoformat() if self._last_check_time else None,
            "last_error": self._last_error,
            "check_count": self._check_count,
            "failure_count": self._failure_count,
            "is_monitoring": self._running,
        }


# Global health checker instance
health_checker = LeanCloudHealthChecker()
