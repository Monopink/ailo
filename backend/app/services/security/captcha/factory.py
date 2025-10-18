"""
CAPTCHA Provider Factory

Creates CAPTCHA provider instances based on configuration.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from services.system_config import get_config
from utils.logging import get_logger
from .base import CaptchaProvider
from .none import NoneCaptchaProvider
from .turnstile import TurnstileProvider

logger = get_logger(__name__)


async def create_captcha_provider(
    provider_type: str,  # 'admin' or 'user'
    db: AsyncSession
) -> CaptchaProvider:
    """
    Create CAPTCHA provider based on configuration.
    
    Reads from system_configs:
    - {provider_type}_captcha_provider: 'none' | 'turnstile'
    - {provider_type}_turnstile_secret_key: Turnstile secret key
    - {provider_type}_captcha_mode: 'strict' | 'fallback' (admin only)
    
    Args:
        provider_type: 'admin' or 'user'
        db: Database session
        
    Returns:
        CAPTCHA provider instance
        
    Raises:
        ValueError: If provider type is not supported
    """
    # Get provider configuration
    captcha_provider = await get_config(
        db,
        key=f"{provider_type}_captcha_provider",
        default="turnstile"
    )
    
    if captcha_provider == "none":
        logger.info(
            "creating_none_captcha_provider",
            provider_type=provider_type
        )
        return NoneCaptchaProvider()
    
    elif captcha_provider == "turnstile":
        # Get Turnstile configuration
        secret_key = await get_config(
            db,
            key=f"{provider_type}_turnstile_secret_key",
            default=""
        )
        
        # Get mode (admin only, default to 'strict' for user)
        if provider_type == "admin":
            mode = await get_config(
                db,
                key="admin_captcha_mode",
                default="strict"
            )
        else:
            mode = "strict"
        
        logger.info(
            "creating_turnstile_provider",
            provider_type=provider_type,
            mode=mode,
            has_secret_key=bool(secret_key)
        )
        
        return TurnstileProvider(secret_key=secret_key, mode=mode)
    
    else:
        error_msg = f"Unsupported CAPTCHA provider: {captcha_provider}"
        logger.error(
            "unsupported_captcha_provider",
            provider_type=provider_type,
            provider=captcha_provider
        )
        raise ValueError(error_msg)

