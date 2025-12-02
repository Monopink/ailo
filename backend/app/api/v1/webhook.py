"""
LeanCloud webhook endpoints.

This module validates webhook authenticity and routes inbound events.
"""

import hashlib
import secrets
import time

from core.config import get_settings
from core.database import get_db
from crud.system import system_configs
from fastapi import APIRouter, Depends, HTTPException, Request, status
from services.message.inbound.router import route_message
from services.message.providers.leancloud.webhook import parse_leancloud_webhook
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/lc-im", tags=["LeanCloud IM Webhook"])

_settings = get_settings()
WEBHOOK_TIMESTAMP_TOLERANCE_MS = 10 * 60 * 1000  # 10 minutes


def _validate_signature(signature_header: str, master_key: str) -> None:
    parts = signature_header.split(",")
    if len(parts) not in (2, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature header"
        )

    signature = parts[0]
    try:
        timestamp_ms = int(parts[1])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature timestamp"
        ) from exc
    nonce = parts[2] if len(parts) == 3 else ""

    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp_ms) > WEBHOOK_TIMESTAMP_TOLERANCE_MS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature expired")

    material = f"{timestamp_ms}{nonce}{master_key}"
    expected = hashlib.md5(material.encode("utf-8")).hexdigest()
    if expected.lower() != signature.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature mismatch")


@router.post("/webhook/{webhook_token}")
async def leancloud_webhook(
    webhook_token: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Receive messages from LeanCloud webhook.

    Security:
    - Validates webhook token from URL path
    - Verifies conversation_id matches system conversation

    Args:
        webhook_token: Security token from URL path
        request: FastAPI request object
        db: Database session

    Returns:
        {"code": 200} on success

    Raises:
        HTTPException: 403 if token invalid, 400 if message invalid
    """
    try:
        # 1. Validate webhook token
        correct_token = await system_configs.get_config_value(
            db, config_key="leancloud_im_webhook_token"
        )

        if not correct_token:
            logger.error("webhook_token_not_configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook not configured",
            )

        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(webhook_token, correct_token):
            logger.warning(
                "invalid_webhook_token_attempt",
                token_prefix=webhook_token[:8] if len(webhook_token) >= 8 else "***",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook token"
            )

        # 2. Validate LeanCloud headers
        app_id = await system_configs.get_config_value(db, config_key="leancloud_im_app_id")
        if not app_id:
            logger.error("leancloud_im_app_id_not_configured_for_webhook")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook not configured",
            )

        lc_id = request.headers.get("X-LC-Id")
        signature_header = request.headers.get("X-LC-Signature")

        if not lc_id or not signature_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing LeanCloud headers"
            )

        if lc_id != app_id:
            logger.warning("leancloud_app_id_mismatch", received=lc_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid LeanCloud App ID"
            )

        _validate_signature(signature_header, _settings.LEANCLOUD_MASTER_KEY)

        # 3. Parse request body (LeanCloud sends array of messages)
        messages = await request.json()

        if not isinstance(messages, list):
            logger.error("invalid_webhook_payload_format", payload_type=type(messages).__name__)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload format"
            )

        logger.info("webhook_messages_received", count=len(messages))

        # 4. Process each message
        processed_count = 0
        for message in messages:
            try:
                # Parse and validate message
                inbound_event = await parse_leancloud_webhook(db, message)

                if inbound_event:
                    # Route to appropriate handler
                    await route_message(db, inbound_event)
                    processed_count += 1

            except Exception as e:
                logger.error(
                    "webhook_message_processing_failed",
                    error=str(e),
                    message_id=message.get("msgId"),
                )
                # Continue processing other messages
                continue

        logger.info("webhook_processing_completed", processed=processed_count, total=len(messages))

        # 5. Return success response (LeanCloud expects {"code": 200})
        return {"code": 200}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("webhook_processing_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )
