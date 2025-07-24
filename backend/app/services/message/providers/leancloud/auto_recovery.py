"""
LeanCloud Conversation Auto Recovery Service

This service handles automatic recovery when conversation ID issues are detected.
It provides mechanisms to:
- Detect conversation ID failures
- Automatically create new conversation IDs
- Update configuration
- Frontend will query for changes automatically
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime

from utils.logging import get_logger
from core.config import settings
from .conversation_logger import conversation_logger, conversation_metrics
from .conversation_auto_setup import create_system_conversation
from .config_manager import set_unified_conversation_id, get_unified_conversation_id

logger = get_logger(__name__)


class ConversationRecoveryService:
    """
    Service for automatic conversation ID recovery.

    This service monitors conversation health and automatically recovers
    from failures by creating new conversation IDs when needed.
    """

    def __init__(self):
        self._recovery_in_progress = False
        self._last_recovery_time: Optional[datetime] = None
        self._recovery_count = 0
        self._recovery_cooldown_seconds = self._get_recovery_cooldown()

    def _get_recovery_cooldown(self) -> int:
        """Get recovery cooldown from environment, no default value"""
        cooldown = getattr(settings, "LEANCLOUD_RECOVERY_COOLDOWN_SECONDS", None)
        if cooldown is None:
            raise ValueError("LEANCLOUD_RECOVERY_COOLDOWN_SECONDS must be configured")
        return int(cooldown)

    async def attempt_recovery(self, failed_conversation_id: str, error_reason: str) -> Optional[str]:
        """
        Attempt to recover from conversation ID failure.

        Args:
            failed_conversation_id: The conversation ID that failed
            error_reason: Reason for the failure

        Returns:
            str: New conversation ID if recovery successful, None otherwise
        """
        if self._recovery_in_progress:
            logger.warning("recovery_already_in_progress", failed_conversation_id=failed_conversation_id)
            return None

        # Check cooldown period
        if self._last_recovery_time:
            time_since_last = (datetime.now() - self._last_recovery_time).total_seconds()
            if time_since_last < self._recovery_cooldown_seconds:
                logger.warning(
                    "recovery_cooldown_active",
                    failed_conversation_id=failed_conversation_id,
                    cooldown_remaining=self._recovery_cooldown_seconds - time_since_last,
                )
                return None

        self._recovery_in_progress = True
        recovery_start_time = time.time()

        try:
            logger.info(
                "starting_conversation_recovery",
                failed_conversation_id=failed_conversation_id,
                error_reason=error_reason,
                recovery_attempt=self._recovery_count + 1,
            )

            conversation_logger.log_conversation_recovery_attempt(
                conversation_id=failed_conversation_id,
                recovery_method="auto_create_new",
                success=False,  # Will update on success
            )

            # Step 1: Create new conversation ID
            new_conversation_id = await self._create_new_conversation()
            if not new_conversation_id:
                raise RuntimeError("Failed to create new conversation ID")

            # Step 2: Update configuration
            await self._update_conversation_config(new_conversation_id)

            # Step 3: Verify new conversation works
            if not await self._verify_new_conversation(new_conversation_id):
                raise RuntimeError("New conversation ID verification failed")

            # Step 4: Record successful recovery
            recovery_duration_ms = int((time.time() - recovery_start_time) * 1000)
            self._recovery_count += 1
            self._last_recovery_time = datetime.now()

            conversation_logger.log_conversation_recovery_attempt(
                conversation_id=new_conversation_id,
                recovery_method="auto_create_new",
                success=True,
                duration_ms=recovery_duration_ms,
            )

            conversation_metrics.record_conversation_operation("recovery_attempts")

            logger.info(
                "conversation_recovery_successful",
                old_conversation_id=failed_conversation_id,
                new_conversation_id=new_conversation_id,
                recovery_duration_ms=recovery_duration_ms,
                total_recoveries=self._recovery_count,
            )

            return new_conversation_id

        except Exception as e:
            recovery_duration_ms = int((time.time() - recovery_start_time) * 1000)

            conversation_logger.log_conversation_recovery_attempt(
                conversation_id=failed_conversation_id,
                recovery_method="auto_create_new",
                success=False,
                duration_ms=recovery_duration_ms,
                error=str(e),
            )

            logger.error(
                "conversation_recovery_failed",
                failed_conversation_id=failed_conversation_id,
                error=str(e),
                recovery_duration_ms=recovery_duration_ms,
                exc_info=True,
            )

            return None

        finally:
            self._recovery_in_progress = False

    async def _create_new_conversation(self) -> Optional[str]:
        """Create a new system conversation"""
        try:
            logger.info("creating_new_system_conversation")
            new_conversation_id = await create_system_conversation()

            if new_conversation_id:
                conversation_logger.log_conversation_created(
                    conversation_id=new_conversation_id, creation_method="auto_recovery"
                )

                logger.info("new_system_conversation_created", conversation_id=new_conversation_id)

            return new_conversation_id

        except Exception as e:
            conversation_logger.log_conversation_creation_failed(
                error=str(e), creation_method="auto_recovery"
            )

            logger.error("failed_to_create_new_conversation", error=str(e), exc_info=True)
            return None

    async def _update_conversation_config(self, new_conversation_id: str) -> None:
        """Update configuration with new conversation ID"""
        try:
            logger.info("updating_conversation_config", new_conversation_id=new_conversation_id)

            # Update the configuration
            set_unified_conversation_id(new_conversation_id)

            # Verify the update
            current_id = get_unified_conversation_id()
            if current_id != new_conversation_id:
                raise RuntimeError(
                    f"Configuration update failed: expected {new_conversation_id}, got {current_id}"
                )

            conversation_logger.log_conversation_cache_operation(
                operation="config_update", conversation_id=new_conversation_id, reason="auto_recovery"
            )

            logger.info("conversation_config_updated", new_conversation_id=new_conversation_id)

        except Exception as e:
            logger.error(
                "failed_to_update_conversation_config",
                new_conversation_id=new_conversation_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def _verify_new_conversation(self, conversation_id: str) -> bool:
        """Verify that the new conversation ID works"""
        try:
            logger.info("verifying_new_conversation", conversation_id=conversation_id)

            # Import health checker to verify the new conversation
            from .leancloud_health_checker import health_checker

            # Perform immediate health check
            health_result = await health_checker.perform_health_check()

            if health_result.get("is_healthy", False):
                logger.info("new_conversation_verification_successful", conversation_id=conversation_id)
                return True
            else:
                logger.error(
                    "new_conversation_verification_failed",
                    conversation_id=conversation_id,
                    health_result=health_result,
                )
                return False

        except Exception as e:
            logger.error(
                "conversation_verification_error",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
            return False

    def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery service status"""
        return {
            "recovery_in_progress": self._recovery_in_progress,
            "last_recovery_time": (
                self._last_recovery_time.isoformat() if self._last_recovery_time else None
            ),
            "recovery_count": self._recovery_count,
            "cooldown_seconds": self._recovery_cooldown_seconds,
        }


# Global recovery service instance
recovery_service = ConversationRecoveryService()
