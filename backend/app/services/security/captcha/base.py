"""
CAPTCHA Provider Protocol

Defines the interface for CAPTCHA providers.
"""

from typing import Protocol


class CaptchaProvider(Protocol):
    """CAPTCHA provider interface"""

    async def verify_token(self, token: str, ip: str) -> tuple[bool, str | None]:
        """
        Verify CAPTCHA token.

        Args:
            token: CAPTCHA token from client
            ip: Client IP address

        Returns:
            (is_valid, error_message)
        """
        ...
