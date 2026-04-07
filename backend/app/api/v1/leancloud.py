"""LeanCloud bootstrap endpoint."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.message import (
    LeanCloudBootstrapConfig,
    LeanCloudBootstrapPresence,
    LeanCloudBootstrapRequest,
    LeanCloudBootstrapResponse,
    LeanCloudBootstrapSignature,
)
from app.services.message.providers.leancloud import service as leancloud_service
from app.services.message.providers.leancloud.config import get_leancloud_runtime_config
from app.services.message.providers.leancloud.presence import upsert_user_presence_endpoint
from app.services.message.providers.leancloud.signature import create_login_signature
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/lc-im", tags=["LeanCloud IM"])

SIGNATURE_ALGORITHM = "HMAC-SHA1"
SIGNATURE_VERSION = "v1"
SIGNATURE_TTL_SECONDS = 3600
REGISTRATION_LEASE_TTL_DAYS = 365


def _build_config_version(*, app_id: str, app_key: str, server_url: str, im_conv_id: str) -> str:
    payload = "|".join(
        [
            app_id,
            app_key,
            server_url,
            im_conv_id,
            SIGNATURE_ALGORITHM,
            SIGNATURE_VERSION,
            str(SIGNATURE_TTL_SECONDS),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@router.post("/bootstrap", response_model=LeanCloudBootstrapResponse)
async def bootstrap_message_session(
    payload: LeanCloudBootstrapRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeanCloudBootstrapResponse:
    """Build complete LeanCloud client session in one call."""
    try:
        runtime_config = await get_leancloud_runtime_config(db, required=True)
        im_conv_id = await leancloud_service.ensure_system_conversation(db)
        user_initialized = await leancloud_service.initialize_user(current_user.qiao_id, db)
        if not user_initialized:
            logger.error("message_session_user_init_failed", user_qiao_id=current_user.qiao_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统错误",
            )

        signature_data = await create_login_signature(
            app_id=runtime_config.app_id, client_id=current_user.qiao_id
        )

        lease_ttl_days = REGISTRATION_LEASE_TTL_DAYS
        endpoint = await upsert_user_presence_endpoint(
            db,
            user_id=int(current_user.id),
            user_qiao_id=current_user.qiao_id,
            client_id=current_user.qiao_id,
            lease_ttl_days=lease_ttl_days,
            client_kind=payload.client_kind,
        )
        await db.commit()
    except Exception as exc:  # pragma: no cover - defensive API guard
        logger.error(
            "message_session_bootstrap_failed",
            user_qiao_id=current_user.qiao_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        ) from exc

    if endpoint.lease_expires_at is None:
        logger.error(
            "message_session_presence_lease_missing",
            user_qiao_id=current_user.qiao_id,
            endpoint_id=int(endpoint.id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )

    server_url = runtime_config.base_url
    if not isinstance(server_url, str) or server_url == "":
        logger.error("message_session_server_url_missing", user_qiao_id=current_user.qiao_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )

    logger.info("message_session_bootstrap_succeeded", user_qiao_id=current_user.qiao_id)

    return LeanCloudBootstrapResponse(
        config_version=_build_config_version(
            app_id=runtime_config.app_id,
            app_key=runtime_config.app_key,
            server_url=server_url,
            im_conv_id=im_conv_id,
        ),
        session=LeanCloudBootstrapConfig(
            client_id=current_user.qiao_id,
            app_id=runtime_config.app_id,
            app_key=runtime_config.app_key,
            server_url=server_url,
            im_conv_id=im_conv_id,
            signature=LeanCloudBootstrapSignature(
                algorithm=SIGNATURE_ALGORITHM,
                version=SIGNATURE_VERSION,
                value=signature_data["signature"],
                timestamp=signature_data["timestamp"],
                nonce=signature_data["nonce"],
                expires_in_ms=SIGNATURE_TTL_SECONDS * 1000,
            ),
        ),
        presence=LeanCloudBootstrapPresence(
            endpoint_id=int(endpoint.id),
            lease_ttl_days=lease_ttl_days,
            lease_expires_at_ms=int(endpoint.lease_expires_at.timestamp() * 1000),
        ),
    )
