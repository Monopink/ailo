"""CAPTCHA provider factory.

This project only enables CAPTCHA for admin authentication.
User-side CAPTCHA is not supported.

Sources:
- Sensitive secret: environment variable `ADMIN_TURNSTILE_SECRET_KEY`
- Operational switches: `system_configs`
  - `admin_captcha_provider`: `none` | `turnstile`
  - `admin_captcha_mode`: `strict` | `fallback` (used when provider is `turnstile`)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.system_config import get_config_str
from app.utils.logging import get_logger

from .base import CaptchaProvider
from .none import NoneCaptchaProvider
from .turnstile import TurnstileProvider

logger = get_logger(__name__)


async def create_captcha_provider(
    provider_type: str,
    db: AsyncSession,
) -> CaptchaProvider:
    if provider_type != "admin":
        raise ValueError(f"Unsupported provider_type: {provider_type}")

    provider_raw = await get_config_str(db, key="admin_captcha_provider")
    provider = provider_raw.strip().lower()

    if not provider or provider == "none":
        logger.info("creating_none_captcha_provider", provider_type=provider_type)
        return NoneCaptchaProvider()

    if provider != "turnstile":
        raise ValueError(f"Unsupported CAPTCHA provider: {provider}")

    mode_raw = await get_config_str(db, key="admin_captcha_mode")
    mode = mode_raw.strip().lower()
    if mode not in ("strict", "fallback"):
        raise ValueError(f"Unsupported admin CAPTCHA mode: {mode}")

    settings = get_settings()
    secret_key = settings.ADMIN_TURNSTILE_SECRET_KEY or ""

    logger.info(
        "creating_turnstile_provider",
        provider_type=provider_type,
        mode=mode,
        has_secret_key=bool(secret_key),
    )
    return TurnstileProvider(secret_key=secret_key, mode=mode)
