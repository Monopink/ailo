"""
Converters for Doubao/OpenAI Responses API payloads.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import MessageConverter

_TEXT_COMPATIBLE_TYPES = {"text", "output_text", "input_text"}


class ResponsesFormatConverter(MessageConverter):
    """Normalizes messages into Responses API compatible blocks."""

    def convert_to_provider_format(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            raw_content = message.get("content")

            if isinstance(raw_content, list):
                content_blocks = self.normalize_content_blocks(raw_content)
            elif raw_content is None:
                content_blocks = []
            else:
                content_blocks = [
                    {
                        "type": "input_text",
                        "text": str(raw_content),
                    }
                ]

            converted.append({"role": role, "content": content_blocks})

        return converted

    def normalize_content_blocks(
        self,
        blocks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []

        for block in blocks:
            if not isinstance(block, dict):
                # Ignore malformed blocks but keep processing the rest
                continue

            block_type = block.get("type")
            if block_type in _TEXT_COMPATIBLE_TYPES:
                normalized.append(
                    {
                        "type": "input_text",
                        "text": block.get("text", ""),
                    }
                )
            else:
                normalized.append(block)

        return normalized
