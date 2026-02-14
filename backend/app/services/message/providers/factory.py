"""Message provider and endpoint-sender factories."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageTransportProvider

from .base import MessageProvider, TimelineEndpointSender
from .leancloud import LeanCloudTimelineSender, create_leancloud_provider
from .websocket import WebSocketTimelineSender

PROVIDER_TYPE_LEANCLOUD = "leancloud"
PROVIDER_TYPE_WEBSOCKET = "websocket"


def resolve_transport_provider(provider_type: str) -> MessageTransportProvider:
    """Resolve provider type string to transport provider enum."""
    normalized = provider_type.strip().lower()
    if normalized == PROVIDER_TYPE_LEANCLOUD:
        return MessageTransportProvider.LEANCLOUD
    if normalized == PROVIDER_TYPE_WEBSOCKET:
        return MessageTransportProvider.WEBSOCKET
    raise ValueError(f"Unsupported provider type: {provider_type}")


def get_default_transport_provider() -> MessageTransportProvider:
    """Get default transport provider enum from configuration."""
    provider_type = os.getenv("DEFAULT_MESSAGE_PROVIDER", PROVIDER_TYPE_LEANCLOUD)
    return resolve_transport_provider(provider_type)


def create_message_provider(db: AsyncSession, provider_type: str | None = None) -> MessageProvider:
    """Create lifecycle-capable message provider instance."""
    selected = (
        provider_type
        if provider_type is not None
        else os.getenv("DEFAULT_MESSAGE_PROVIDER", PROVIDER_TYPE_LEANCLOUD)
    )
    if selected is None:
        raise ValueError("DEFAULT_MESSAGE_PROVIDER is not configured.")
    normalized = selected.strip().lower()
    if normalized == PROVIDER_TYPE_LEANCLOUD:
        return create_leancloud_provider(db)
    raise ValueError(f"Unsupported provider type: {selected}")


def get_default_provider(db: AsyncSession) -> MessageProvider:
    """Get default lifecycle provider from configuration."""
    return create_message_provider(db)


def create_timeline_endpoint_sender(
    db: AsyncSession,
    *,
    provider: MessageTransportProvider,
) -> TimelineEndpointSender:
    """Create endpoint sender by transport provider enum."""
    if provider == MessageTransportProvider.WEBSOCKET:
        return WebSocketTimelineSender()
    if provider == MessageTransportProvider.LEANCLOUD:
        return LeanCloudTimelineSender(db)
    raise ValueError(f"Unsupported provider enum: {provider}")
