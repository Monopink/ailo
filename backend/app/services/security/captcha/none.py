"""
None CAPTCHA Provider

Disables CAPTCHA verification (always returns True).
"""

from app.utils.logging import get_logger

logger = get_logger(__name__)


class NoneCaptchaProvider:
    """
    No CAPTCHA verification.

    Always returns True, effectively disabling CAPTCHA.
    """

    def __init__(self):
        """Initialize none CAPTCHA provider"""
        logger.info("none_captcha_provider_initialized")

    async def verify_token(self, token: str, ip: str) -> tuple[bool, str | None]:
        """
        Always return True (no verification).

        Args:
            token: CAPTCHA token (ignored)
            ip: Client IP (ignored)

        Returns:
            (True, None)
        """
        return True, None
