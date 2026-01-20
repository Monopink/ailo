"""LeanCloud webhook endpoints.

This module validates webhook tokens and routes inbound events.
"""

import secrets

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.system import system_configs
from app.services.message.inbound.router import route_message
from app.services.message.providers.leancloud.webhook import parse_leancloud_webhook
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/leancloud", tags=["LeanCloud IM Webhook"])

_TOKEN_PREFIX_LENGTH = 8


@router.post("/webhook/{webhook_token}")
async def leancloud_webhook(
    webhook_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Receive messages from LeanCloud webhook.

    Security:
    - Validates webhook token from URL path

    Args:
        webhook_token: Security token from URL path
        request: FastAPI request object
        db: Database session

    Returns:
        {"code": 200} on success

    """
    # 1. Validate webhook token
    correct_token = await system_configs.get_config_value(
        db, config_key="leancloud_im_webhook_token"
    )

    if not isinstance(correct_token, str) or not correct_token:
        logger.error("webhook_token_not_configured")
        return {"code": 200}
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(webhook_token, correct_token):
        logger.warning(
            "invalid_webhook_token_attempt",
            token_prefix=(
                webhook_token[:_TOKEN_PREFIX_LENGTH]
                if len(webhook_token) >= _TOKEN_PREFIX_LENGTH
                else "***"
            ),
        )
        return {"code": 200}

    # 2. Parse request body (LeanCloud sends array of messages)
    try:
        messages = await request.json()
    except Exception as exc:
        logger.error("invalid_webhook_payload_json", error=str(exc))
        return {"code": 200}

    if not isinstance(messages, list):
        logger.error("invalid_webhook_payload_format", payload_type=type(messages).__name__)
        return {"code": 200}

    logger.info("webhook_messages_received", count=len(messages))

    # 3. Process each message
    processed_count = 0
    for message in messages:
        try:
            inbound_event = await parse_leancloud_webhook(db, message)

            if inbound_event:
                await route_message(db, inbound_event)
                processed_count += 1

        except Exception:
            message_id = message.get("msgId") if isinstance(message, dict) else None
            logger.exception("webhook_message_processing_failed", message_id=message_id)
            continue

    logger.info("webhook_processing_completed", processed=processed_count, total=len(messages))

    # 4. Return success response (LeanCloud expects {"code": 200})
    return {"code": 200}
