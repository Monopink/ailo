"""
Public system endpoints (no auth) for client bootstrapping configs.
"""

from core.database import get_db
from crud.system import system_configs
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/system", tags=["System Public"])


@router.get("/captcha-config")
async def get_captcha_config(request: Request, db: AsyncSession = Depends(get_db)):
    """Return public captcha configuration for clients.

    Only non-sensitive values are returned.
    """
    # Detect client from header (e.g., 'wxminipg')
    client = (request.headers.get("X-Client", "") or "").strip().lower()

    provider = None
    scene_id = None

    # Prefer client-specific keys (new scheme without 'user_')
    if client:
        provider = await system_configs.get_config_value(
            db, config_key=f"{client}_captcha_provider"
        )
        scene_id = await system_configs.get_config_value(
            db, config_key=f"{client}_aliyun_captcha_scene_id"
        )

    # Backward compatibility fallbacks
    if not provider:
        provider = await system_configs.get_config_value(db, config_key="captcha_provider")
    if not provider:
        provider = await system_configs.get_config_value(db, config_key="user_captcha_provider")

    if not scene_id:
        # Older client-specific key
        if client:
            scene_id = await system_configs.get_config_value(
                db, config_key=f"aliyun_{client}_captcha_scene_id"
            )
    if not scene_id:
        scene_id = await system_configs.get_config_value(db, config_key="aliyun_captcha_scene_id")

    # Region is hardcoded to 'cn' per current product decision
    return {
        "provider": (provider or "aliyun").lower(),
        "scene_id": scene_id or "",
        "region": "cn",
        "mode": "popup",
        "language": "cn",
    }
