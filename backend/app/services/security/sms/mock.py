"""
Mock SMS Provider

Logs SMS to application logs for testing purposes.
"""

import time

from app.utils.logging import get_logger

from .base import SMSResult

PHONE_MASK_PREFIX_LEN = 3
PHONE_MASK_SUFFIX_LEN = 2
PHONE_MASK_THRESHOLD = 5

logger = get_logger(__name__)


class MockSMSProvider:
    """
    Mock SMS provider for testing.

    Logs SMS messages to application logs instead of sending real SMS.
    """

    def __init__(self) -> None:
        """Initialize mock SMS provider"""
        logger.info("mock_sms_provider_initialized")

    async def send_verification_code(self, phone: str, code: str) -> SMSResult:
        """
        Log SMS to application logs.

        Args:
            phone: Phone number
            code: Verification code

        Returns:
            SMSResult with success status
        """
        # Mask phone number for privacy (show first 3 and last 2 digits)
        masked_phone = (
            f"{phone[:PHONE_MASK_PREFIX_LEN]}****{phone[-PHONE_MASK_SUFFIX_LEN:]}"
            if len(phone) > PHONE_MASK_THRESHOLD
            else "***"
        )

        # Log SMS (include full phone for testing convenience)
        logger.info(
            "mock_sms_sent",
            phone=masked_phone,
            code=code,
            full_phone=phone,  # For testing - remove in production
            timestamp=time.time(),
        )

        # Generate mock provider ID
        provider_id = f"mock_{int(time.time() * 1000)}"

        return SMSResult(success=True, provider_id=provider_id, error_code=None, error_message=None)

    async def check_health(self) -> tuple[bool, str | None]:
        """
        Check provider health (always healthy for mock).

        Returns:
            (True, None)
        """
        return True, None
