"""
Converters for Doubao/OpenAI Responses API payloads.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import MessageConverter


class ResponsesFormatConverter(MessageConverter):
    """Convert business-format messages into Doubao Responses API payloads."""

    def convert_to_provider_format(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            blocks = self._convert_message_to_blocks(message)
            if not blocks:
                continue

            if converted and converted[-1]["role"] == role:
                converted[-1]["content"].extend(blocks)
            else:
                converted.append({"role": role, "content": blocks})

        return converted

    def _convert_message_to_blocks(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        message_type = (message.get("message_type") or "text").lower()
        if message_type == "text":
            text = message.get("text_content") or ""
            return [{"type": "input_text", "text": text}]

        if message_type == "image":
            media_url = message.get("media_url")
            if not media_url:
                return []
            return [{"type": "input_image", "image_url": {"url": media_url}}]

        if message_type == "audio":
            metadata: Optional[Dict[str, Any]] = message.get("media_metadata") or {}
            transcript = metadata.get("transcript") or "[Audio message]"
            return [{"type": "input_text", "text": f"[语音消息: {transcript}]"}]

        # Fallback: avoid failing the entire payload
        return [{"type": "input_text", "text": "[Unsupported message type]"}]
