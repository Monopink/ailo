"""
System endpoints for client bootstrapping configs.
"""

from typing import TypedDict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.security.captcha.factory import create_captcha_provider_for_request

router = APIRouter(prefix="/system", tags=["System"])

settings = get_settings()
ALLOWED_CLIENTS = {
    client.strip().lower()
    for client in settings.CAPTCHA_CLIENT_WHITELIST
    if client and client.strip()
}


class CaptchaConfigResponse(TypedDict):
    provider: str
    scene_id: str
    region: str
    mode: str
    language: str
    provider_version: str
    require_human_verification: bool


def _require_client_id(request: Request) -> str:
    client = (request.headers.get("X-Client", "") or "").strip().lower()
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 X-Client header")
    if ALLOWED_CLIENTS and client not in ALLOWED_CLIENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="客户端未授权",
        )
    return client


@router.get("/captcha-config")
async def get_captcha_config(
    request: Request, db: AsyncSession = Depends(get_db)
) -> CaptchaConfigResponse:
    """Return public captcha configuration for clients."""

    _require_client_id(request)
    _, metadata = await create_captcha_provider_for_request("user", db, request)
    return metadata.to_response()  # type: ignore[return-value]
