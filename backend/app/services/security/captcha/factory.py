"""
CAPTCHA Provider Factory

Creates CAPTCHA provider instances based on configuration.

System Architecture:
- Admin Backend: Uses Turnstile (configured via admin_captcha_provider='turnstile')
- User/Clients: Currently disabled (provider='none', no human verification required)
- Future Extension: Supports client-specific providers via X-Client header
  (e.g., X-Client: wxminipg → reads wxminipg_captcha_provider config)

Design Principles:
- Factory Pattern: Easy to add new providers (reCAPTCHA, hCaptcha, etc.)
- No user-side verification in MVP: Small-scale launch, fraud risk low
- Reserved config mechanism for future clients (mobile app, web, etc.)

Supported Providers:
- 'none': No verification (NoneCaptchaProvider)
- 'turnstile': Cloudflare Turnstile (TurnstileProvider)
"""

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_config_str
from app.utils.logging import get_logger

from .base import CaptchaProvider
from .none import NoneCaptchaProvider
from .turnstile import TurnstileProvider

logger = get_logger(__name__)


@dataclass
class CaptchaRuntimeMetadata:
    provider: str
    provider_version: str
    scene_id: str | None
    region: str
    mode: str
    language: str = "cn"
    require_human_verification: bool = True

    def to_response(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "scene_id": self.scene_id or "",
            "region": self.region,
            "mode": self.mode,
            "language": self.language,
            "require_human_verification": self.require_human_verification,
        }


def _resolve_provider_version(provider: str) -> str:
    mapping = {"turnstile": "turnstile-v1", "none": "none"}
    normalized = provider.lower()
    return mapping.get(normalized, normalized)


async def _create_provider_by_name(
    provider_name: str | None,
    provider_type: str,
    db: AsyncSession,
    *,
    client_id: str | None = None,
) -> tuple[CaptchaProvider, CaptchaRuntimeMetadata]:
    provider_normalized = (provider_name or "none").lower()

    if provider_normalized == "none":
        logger.info(
            "creating_none_captcha_provider",
            provider_type=provider_type,
            client=client_id,
        )
        metadata = CaptchaRuntimeMetadata(
            provider="none",
            provider_version=_resolve_provider_version("none"),
            scene_id="",
            region="",
            mode="disabled",
            require_human_verification=False,
        )
        return NoneCaptchaProvider(), metadata

    if provider_normalized == "turnstile":
        if client_id:
            secret_key = await get_config_str(
                db,
                key=f"{client_id}_turnstile_secret_key",
                required=False,
                default="",
            )
            if not secret_key:
                secret_key = await get_config_str(
                    db,
                    key="turnstile_secret_key",
                    required=False,
                    default="",
                )
        else:
            secret_key = await get_config_str(
                db,
                key=f"{provider_type}_turnstile_secret_key",
                required=False,
                default="",
            )
            if not secret_key:
                secret_key = await get_config_str(
                    db,
                    key="turnstile_secret_key",
                    required=False,
                    default="",
                )

        mode = (
            await get_config_str(db, key="admin_captcha_mode")
            if provider_type == "admin"
            else "strict"
        )
        logger.info(
            "creating_turnstile_provider",
            provider_type=provider_type,
            client=client_id,
            mode=mode,
            has_secret_key=bool(secret_key),
        )
        provider = TurnstileProvider(secret_key=secret_key or "", mode=mode)
        metadata = CaptchaRuntimeMetadata(
            provider="turnstile",
            provider_version=_resolve_provider_version("turnstile"),
            scene_id="",
            region="global",
            mode=mode,
        )
        return provider, metadata

    error_msg = f"Unsupported CAPTCHA provider: {provider_normalized}"
    logger.error(
        "unsupported_captcha_provider",
        provider_type=provider_type,
        provider=provider_normalized,
        client=client_id,
    )
    raise ValueError(error_msg)


async def create_captcha_provider(
    provider_type: str,
    db: AsyncSession,  # 'admin' or 'user'
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
    captcha_provider = await get_config_str(
        db,
        key=f"{provider_type}_captcha_provider",
    )

    provider, _ = await _create_provider_by_name(captcha_provider, provider_type, db)
    return provider


async def create_captcha_provider_for_request(
    provider_type: str,
    db: AsyncSession,
    request: Request | None = None,
) -> tuple[CaptchaProvider, CaptchaRuntimeMetadata]:
    """
    Create CAPTCHA provider with client override support.

    If header X-Client is provided (e.g., 'wxminipg'),
    try reading client-specific provider key first:
    - {provider_type}_{client}_captcha_provider
    Fallback to the generic {provider_type}_captcha_provider.

    SceneId can optionally be overridden via
    - {client}_captcha_scene_id
    falling back to 'captcha_scene_id'.
    """
    client_id = None
    if request is not None:
        try:
            client_id = (request.headers.get("X-Client", "") or "").strip().lower()
        except Exception:
            client_id = None

    # Try client-specific provider key first (new scheme without 'user_' prefix)
    if client_id:
        provider_key = f"{client_id}_captcha_provider"
        captcha_provider = await get_config_str(
            db,
            key=provider_key,
            required=False,
            default="",
        )
        if captcha_provider:
            return await _create_provider_by_name(
                captcha_provider, provider_type, db, client_id=client_id
            )

    captcha_provider = await get_config_str(
        db,
        key=f"{provider_type}_captcha_provider",
    )
    return await _create_provider_by_name(captcha_provider, provider_type, db)
