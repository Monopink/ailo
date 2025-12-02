"""
SMS Provider Protocol

Defines the interface for SMS providers.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SMSResult:
    """SMS operation result"""

    success: bool
    provider_id: str | None  # Provider-specific message ID
    error_code: str | None
    error_message: str | None


class SMSProvider(Protocol):
    """SMS provider interface"""

    async def send_verification_code(self, phone: str, code: str) -> SMSResult:
        """
        Send verification code SMS.

        Args:
            phone: Phone number (with country code)
            code: Verification code

        Returns:
            SMSResult with operation status
        """
        ...

    async def check_health(self) -> tuple[bool, str | None]:
        """
        Check provider service health.

        Returns:
            (is_healthy, error_message)
        """
        ...
