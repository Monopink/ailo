"""
Cloudflare Turnstile CAPTCHA Provider

Verifies CAPTCHA tokens using Cloudflare Turnstile API.
"""

from typing import Tuple, Optional
import httpx

from utils.logging import get_logger

logger = get_logger(__name__)


class TurnstileProvider:
    """
    Cloudflare Turnstile CAPTCHA provider.
    
    Verifies CAPTCHA tokens via Cloudflare's siteverify API.
    """
    
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    
    def __init__(self, secret_key: str, mode: str = 'strict'):
        """
        Initialize Turnstile provider.
        
        Args:
            secret_key: Turnstile secret key
            mode: Verification mode
                - 'strict': Block on any error (default)
                - 'fallback': Allow on service errors, block only on invalid token
        """
        self.secret_key = secret_key
        self.mode = mode
        
        logger.info(
            "turnstile_provider_initialized",
            mode=mode,
            has_secret_key=bool(secret_key)
        )
    
    async def verify_token(
        self,
        token: str,
        ip: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify Turnstile token.
        
        Args:
            token: Turnstile token from client
            ip: Client IP address
            
        Returns:
            (is_valid, error_message)
        """
        if not self.secret_key:
            error_msg = "Turnstile secret key not configured"
            logger.error("turnstile_secret_key_missing")
            
            if self.mode == 'fallback':
                # Allow in fallback mode if service not configured
                logger.warning("turnstile_verification_skipped_fallback_mode")
                return True, None
            else:
                return False, error_msg
        
        if not token:
            return False, "CAPTCHA token is required"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.VERIFY_URL,
                    data={
                        "secret": self.secret_key,
                        "response": token,
                        "remoteip": ip
                    }
                )
                
                if response.status_code != 200:
                    error_msg = f"Turnstile API error: HTTP {response.status_code}"
                    logger.error(
                        "turnstile_api_error",
                        status_code=response.status_code,
                        response_text=response.text[:200]
                    )
                    
                    if self.mode == 'fallback':
                        # Allow in fallback mode on service errors
                        logger.warning("turnstile_verification_allowed_fallback_mode")
                        return True, None
                    else:
                        return False, error_msg
                
                result = response.json()
                
                if result.get("success"):
                    logger.info(
                        "turnstile_verification_success",
                        ip=ip,
                        challenge_ts=result.get("challenge_ts"),
                        hostname=result.get("hostname")
                    )
                    return True, None
                else:
                    error_codes = result.get("error-codes", [])
                    error_msg = f"CAPTCHA verification failed: {', '.join(error_codes)}"
                    
                    logger.warning(
                        "turnstile_verification_failed",
                        ip=ip,
                        error_codes=error_codes
                    )
                    
                    return False, error_msg
        
        except httpx.TimeoutException:
            error_msg = "CAPTCHA verification timeout"
            logger.error("turnstile_timeout", ip=ip)
            
            if self.mode == 'fallback':
                # Allow in fallback mode on timeout
                logger.warning("turnstile_timeout_allowed_fallback_mode")
                return True, None
            else:
                return False, error_msg
        
        except Exception as e:
            error_msg = f"CAPTCHA verification error: {str(e)}"
            logger.error(
                "turnstile_unexpected_error",
                ip=ip,
                error=str(e),
                error_type=type(e).__name__
            )
            
            if self.mode == 'fallback':
                # Allow in fallback mode on unexpected errors
                logger.warning("turnstile_error_allowed_fallback_mode")
                return True, None
            else:
                return False, error_msg

