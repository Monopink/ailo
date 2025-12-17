"""
System endpoints for client bootstrapping configs.
"""

from typing import TypedDict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.system import system_configs

router = APIRouter(prefix="/system", tags=["System"])


class CaptchaConfigResponse(TypedDict):
    provider: str
    scene_id: str
    region: str
    mode: str
    language: str


@router.get("/captcha-config")
async def get_captcha_config(
    request: Request, db: AsyncSession = Depends(get_db)
) -> CaptchaConfigResponse:
    """Return public captcha configuration for clients."""

    client = (request.headers.get("X-Client", "") or "").strip().lower()

    provider = None
    scene_id = None

    if client:
        provider = await system_configs.get_config_value(
            db, config_key=f"{client}_captcha_provider"
        )
        scene_id = await system_configs.get_config_value(
            db, config_key=f"{client}_aliyun_captcha_scene_id"
        )

    if not provider:
        provider = await system_configs.get_config_value(db, config_key="captcha_provider")
    if not provider:
        provider = await system_configs.get_config_value(db, config_key="user_captcha_provider")

    if not scene_id and client:
        scene_id = await system_configs.get_config_value(
            db, config_key=f"aliyun_{client}_captcha_scene_id"
        )
    if not scene_id:
        scene_id = await system_configs.get_config_value(db, config_key="aliyun_captcha_scene_id")

    return {
        "provider": (provider or "aliyun").lower(),
        "scene_id": scene_id or "",
        "region": "cn",
        "mode": "popup",
        "language": "cn",
    }
