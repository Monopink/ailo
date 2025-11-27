"""
CAPTCHA Provider Factory

Creates CAPTCHA provider instances based on configuration.
"""

from typing import Optional

from fastapi import Request
from services.system_config import get_config
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

from .aliyun import AliyunCaptchaProvider
from .base import CaptchaProvider
from .none import NoneCaptchaProvider
from .turnstile import TurnstileProvider

logger = get_logger(__name__)


async def create_captcha_provider(
    provider_type: str, db: AsyncSession  # 'admin' or 'user'
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
    captcha_provider = await get_config(db, key=f"{provider_type}_captcha_provider")

    if captcha_provider == "none":
        logger.info("creating_none_captcha_provider", provider_type=provider_type)
        return NoneCaptchaProvider()

    elif captcha_provider == "turnstile":
        # Get Turnstile configuration
        secret_key = await get_config(db, key=f"{provider_type}_turnstile_secret_key")

        # Get mode (admin only, default to 'strict' for user)
        if provider_type == "admin":
            mode = await get_config(db, key="admin_captcha_mode")
        else:
            mode = "strict"

        logger.info(
            "creating_turnstile_provider",
            provider_type=provider_type,
            mode=mode,
            has_secret_key=bool(secret_key),
        )

        return TurnstileProvider(secret_key=secret_key, mode=mode)

    elif captcha_provider == "aliyun":
        # Region is fixed to 'cn' (MVP decision)
        region = "cn"
        # Single scene id managed via DB for simplicity
        scene_id = await get_config(
            db,
            key="aliyun_captcha_scene_id",
        )
        logger.info(
            "creating_aliyun_captcha_provider",
            provider_type=provider_type,
            region=region,
            has_scene_id=bool(scene_id),
        )
        return AliyunCaptchaProvider(scene_id=scene_id, region=region, mode="strict")

    else:
        error_msg = f"Unsupported CAPTCHA provider: {captcha_provider}"
        logger.error("unsupported_captcha_provider", provider_type=provider_type, provider=captcha_provider)
        raise ValueError(error_msg)


async def create_captcha_provider_for_request(
    provider_type: str,
    db: AsyncSession,
    request: Optional[Request] = None,
) -> CaptchaProvider:
    """
    Create CAPTCHA provider with client override support.

    If header X-Client is provided (e.g., 'wxminipg'),
    try reading client-specific provider key first:
    - {provider_type}_{client}_captcha_provider
    Fallback to the generic {provider_type}_captcha_provider.

    For Aliyun, SceneId can optionally be overridden via
    - aliyun_{client}_captcha_scene_id
    falling back to 'aliyun_captcha_scene_id'. Region is fixed to 'cn'.
    """
    client_id = None
    if request is not None:
        try:
            client_id = (request.headers.get("X-Client", "") or "").strip().lower()
        except Exception:
            client_id = None

    # Try client-specific provider key first (new scheme without 'user_' prefix)
    if client_id:
        # e.g. wxminipg_captcha_provider
        provider_key = f"{client_id}_captcha_provider"
        captcha_provider = await get_config(db, key=provider_key, required=False)
        if captcha_provider:
            if captcha_provider == "none":
                logger.info(
                    "creating_none_captcha_provider_client",
                    provider_type=provider_type,
                    client=client_id,
                )
                return NoneCaptchaProvider()
            elif captcha_provider == "turnstile":
                # Prefer client-specific secret, fallback to generic
                secret_key = await get_config(
                    db,
                    key=f"{client_id}_turnstile_secret_key",
                    required=False,
                )
                if not secret_key:
                    secret_key = await get_config(db, key="turnstile_secret_key")
                mode = (
                    "strict"
                    if provider_type != "admin"
                    else (await get_config(db, key="admin_captcha_mode"))
                )
                logger.info(
                    "creating_turnstile_provider_client",
                    provider_type=provider_type,
                    client=client_id,
                    mode=mode,
                    has_secret_key=bool(secret_key),
                )
                return TurnstileProvider(secret_key=secret_key, mode=mode)
            elif captcha_provider == "aliyun":
                region = "cn"
                # Optional client-specific SceneId (e.g. wxminipg_aliyun_captcha_scene_id)
                scene_id = await get_config(
                    db,
                    key=f"{client_id}_aliyun_captcha_scene_id",
                    required=False,
                )
                if not scene_id:
                    # Backward compatibility keys
                    scene_id = await get_config(
                        db, key=f"aliyun_{client_id}_captcha_scene_id", required=False
                    )
                if not scene_id:
                    scene_id = await get_config(db, key="aliyun_captcha_scene_id")
                logger.info(
                    "creating_aliyun_captcha_provider_client",
                    provider_type=provider_type,
                    client=client_id,
                    region=region,
                    has_scene_id=bool(scene_id),
                )
                return AliyunCaptchaProvider(scene_id=scene_id, region=region, mode="strict")

    # Fallback to generic selection
    return await create_captcha_provider(provider_type, db)
