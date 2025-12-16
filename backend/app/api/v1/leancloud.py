"""
LeanCloud IM configuration and signature endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.crud.system import system_configs
from app.models.user import User
from app.schemas.message import (
    LeanCloudConfigResponse,
    LeanCloudSignatureRequest,
    LeanCloudSignatureResponse,
)
from app.services.message.providers.leancloud import service as leancloud_service
from app.services.message.providers.leancloud.signature import create_login_signature
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/lc-im", tags=["LeanCloud IM"])

_settings = get_settings()
SIGNATURE_ALGORITHM = "HMAC-SHA1"
SIGNATURE_VERSION = "v1"
SIGNATURE_TTL_SECONDS = getattr(_settings, "LEAN_CLOUD_SIGNATURE_TTL_SECONDS", 3600)


@router.get("/config", response_model=LeanCloudConfigResponse)
async def get_lc_im_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeanCloudConfigResponse:
    """
    Return LeanCloud IM configuration required by clients.
    """

    state = await leancloud_service.get_conversation_registry_state(db)

    # Type guard: validate im_conv_id from JSONDict
    im_conv_id_raw = state.get("im_conv_id")
    if not isinstance(im_conv_id_raw, str) or not im_conv_id_raw:
        logger.error(
            "invalid_im_conv_id_type", value=im_conv_id_raw, user_qiao_id=current_user.qiao_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid system configuration"
        )

    im_conv_id: str = im_conv_id_raw

    logger.info("lc_im_config_retrieved", user_qiao_id=current_user.qiao_id)

    return LeanCloudConfigResponse(
        im_conv_id=im_conv_id,
        signature_algorithm=SIGNATURE_ALGORITHM,
        signature_version=SIGNATURE_VERSION,
        signature_ttl_ms=SIGNATURE_TTL_SECONDS * 1000,
    )


@router.post("/signature", response_model=LeanCloudSignatureResponse)
async def generate_lc_im_signature(
    payload: LeanCloudSignatureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeanCloudSignatureResponse:
    """
    Generate LeanCloud IM login signature for the authenticated client.
    """

    if payload.client_id != current_user.qiao_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="客户端ID与当前用户不匹配"
        )

    app_id = await system_configs.get_config_value(db, config_key="leancloud_im_app_id")
    if not app_id:
        logger.error("leancloud_im_app_id_not_configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="消息服务未配置",
        )

    signature_data = await create_login_signature(app_id=app_id, client_id=payload.client_id)

    logger.info("lc_im_signature_generated", client_id=payload.client_id)

    return LeanCloudSignatureResponse(
        client_id=payload.client_id,
        signature=signature_data["signature"],
        timestamp=signature_data["timestamp"],
        nonce=signature_data["nonce"],
        expires_in=SIGNATURE_TTL_SECONDS,
    )
