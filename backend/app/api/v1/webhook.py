"""LeanCloud webhook endpoints.

This module validates webhook authenticity and routes inbound events.
"""

import hashlib
import secrets
import time
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.crud.system import system_configs
from app.services.message.inbound.router import route_message
from app.services.message.providers.leancloud.webhook import parse_leancloud_webhook
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/leancloud", tags=["LeanCloud IM Webhook"])

_settings = get_settings()
WEBHOOK_TIMESTAMP_TOLERANCE_MS = 10 * 60 * 1000  # 10 minutes
_SIGNATURE_PARTS_WITH_NONCE = 3
_TOKEN_PREFIX_LENGTH = 8


def _raise_invalid_signature_header() -> None:
    """Raise HTTPException for invalid signature header."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature header")


def _raise_invalid_signature_timestamp() -> None:
    """Raise HTTPException for invalid signature timestamp."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature timestamp")


def _raise_signature_expired() -> None:
    """Raise HTTPException for expired signature."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature expired")


def _raise_signature_mismatch() -> None:
    """Raise HTTPException for signature mismatch."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature mismatch")


def _validate_signature(signature_header: str, master_key: str) -> None:
    """Validate LeanCloud webhook signature.

    Note: Uses MD5 as required by LeanCloud's webhook signature protocol.
    This is not a security concern as it's used for HMAC-like verification,
    not for cryptographic hashing.
    """
    parts = signature_header.split(",")
    if len(parts) not in (2, 3):
        _raise_invalid_signature_header()

    signature = parts[0]
    try:
        timestamp_ms = int(parts[1])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature timestamp"
        ) from exc
    nonce = parts[2] if len(parts) == _SIGNATURE_PARTS_WITH_NONCE else ""

    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp_ms) > WEBHOOK_TIMESTAMP_TOLERANCE_MS:
        _raise_signature_expired()

    material = f"{timestamp_ms}{nonce}{master_key}"
    # MD5 is required by LeanCloud's signature protocol (not a security issue here)
    expected = hashlib.md5(material.encode("utf-8"), usedforsecurity=False).hexdigest()
    if expected.lower() != signature.lower():
        _raise_signature_mismatch()


def _raise_webhook_not_configured() -> None:
    """Raise HTTPException for webhook not configured."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Webhook not configured",
    )


def _raise_invalid_webhook_token() -> None:
    """Raise HTTPException for invalid webhook token."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook token")


def _raise_invalid_leancloud_app_id() -> None:
    """Raise HTTPException for invalid LeanCloud App ID."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid LeanCloud App ID")


def _raise_invalid_payload_format() -> None:
    """Raise HTTPException for invalid payload format."""
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload format")


@router.post("/webhook/{webhook_token}")
async def leancloud_webhook(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Receive messages from LeanCloud webhook.

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

        if not isinstance(correct_token, str):
            logger.error("webhook_token_not_configured")
            _raise_webhook_not_configured()
        correct_token_str = cast(str, correct_token)

        if not correct_token_str:
            logger.error("webhook_token_not_configured")
            _raise_webhook_not_configured()

        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(webhook_token, correct_token_str):
            logger.warning(
                "invalid_webhook_token_attempt",
                token_prefix=(
                    webhook_token[:_TOKEN_PREFIX_LENGTH]
                    if len(webhook_token) >= _TOKEN_PREFIX_LENGTH
                    else "***"
                ),
            )
            _raise_invalid_webhook_token()

        # 2. Validate LeanCloud headers
        app_id = await system_configs.get_config_value(db, config_key="leancloud_im_app_id")

        if not isinstance(app_id, str):
            logger.error("leancloud_im_app_id_not_configured_for_webhook")
            _raise_webhook_not_configured()
        if not app_id:
            logger.error("leancloud_im_app_id_not_configured_for_webhook")
            _raise_webhook_not_configured()

        lc_id = request.headers.get("X-LC-Id")
        signature_header = request.headers.get("X-LC-Signature")

        if not lc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing X-LC-Id header"
            )
        if not signature_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing X-LC-Signature header"
            )

        if lc_id != app_id:
            logger.warning("leancloud_app_id_mismatch", received=lc_id)
            _raise_invalid_leancloud_app_id()

        _validate_signature(signature_header, _settings.LEANCLOUD_MASTER_KEY)

        # 3. Parse request body (LeanCloud sends array of messages)
        messages = await request.json()

        if not isinstance(messages, list):
            logger.error("invalid_webhook_payload_format", payload_type=type(messages).__name__)
            _raise_invalid_payload_format()

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

            except Exception:
                logger.exception(
                    "webhook_message_processing_failed",
                    message_id=message.get("msgId"),
                )
                # Continue processing other messages
                continue

        logger.info("webhook_processing_completed", processed=processed_count, total=len(messages))

    except HTTPException:
        raise
    except Exception:
        logger.exception("webhook_processing_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from None

    # 5. Return success response (LeanCloud expects {"code": 200})
    return {"code": 200}
