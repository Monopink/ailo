"""
CAPTCHA Provider Protocol

Defines the interface for CAPTCHA providers.
"""

from typing import Protocol, Tuple, Optional


class CaptchaProvider(Protocol):
    """CAPTCHA provider interface"""
    
    async def verify_token(
        self,
        token: str,
        ip: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify CAPTCHA token.
        
        Args:
            token: CAPTCHA token from client
            ip: Client IP address
            
        Returns:
            (is_valid, error_message)
        """
        ...

