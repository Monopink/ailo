"""
LeanMessage webhook handlers for chat_service.
Handles incoming webhook requests from LeanMessage system conversations.
"""

import json
from typing import Dict, Any, List
from fastapi import Request
from ..utils.logging import get_logger
from ..services.leanmessage import leanmessage_service

logger = get_logger(__name__)


async def handle_leanmessage_webhook(request: Request) -> Dict[str, str]:
    """
    Handle LeanMessage webhook for incoming messages from system conversations.

    LeanMessage sends webhook data in this format:
    [
        {
            "fromIp": "121.238.214.92",
            "conv": {"__type": "Pointer", "className": "_Conversation", "objectId": "55b99ad700b0387b8a3d7bf0"},
            "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
            "from": "A",
            "bin": false,
            "data": "消息内容",
            "createdAt": {"__type": "Date", "iso": "2015-07-30T14:37:42.584Z"},
            "updatedAt": {"__type": "Date", "iso": "2015-07-30T14:37:42.584Z"}
        }
    ]
    """
    try:
        # Get raw body
        body = await request.body()
        messages = json.loads(body.decode("utf-8"))

        logger.info("leanmessage_webhook_received", data=messages)

        # Process each message
        for message_data in messages:
            await process_leanmessage_message(message_data)

        return {"status": "ok"}

    except Exception as e:
        logger.error("leanmessage_webhook_error", error=str(e), exc_info=True)
        return {"status": "error", "message": str(e)}


async def process_leanmessage_message(message_data: Dict[str, Any]) -> None:
    """
    Process a single LeanMessage webhook message using leanmessage service.
    """
    try:
        # Use leanmessage service to process the message
        await leanmessage_service.process_webhook_message(message_data)

    except Exception as e:
        logger.error(
            "process_leanmessage_message_error", error=str(e), message_data=message_data, exc_info=True
        )
