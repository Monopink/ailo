"""
Abstract interfaces for message format converters.

The converters allow adapters to normalize conversation history into the
provider-specific payload shape while keeping storage and upstream logic
agnostic to those details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MessageConverter(ABC):
    """Base class for converting message payloads."""

    @abstractmethod
    def convert_to_provider_format(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert generic messages into provider specific format.
        """
