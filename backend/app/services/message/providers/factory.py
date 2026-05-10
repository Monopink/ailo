"""Message provider and endpoint-sender factories."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageTransportProvider

from .base import TimelineEndpointSender
from .websocket import WebSocketTimelineSender

PROVIDER_TYPE_WEBSOCKET = "websocket"
DEFAULT_PROVIDER_TYPE = PROVIDER_TYPE_WEBSOCKET

_PROVIDER_TYPE_REGISTRY: dict[str, MessageTransportProvider] = {}
_TIMELINE_SENDER_REGISTRY: dict[
    MessageTransportProvider,
    Callable[[AsyncSession], TimelineEndpointSender],
] = {}


def register_transport_provider_type(
    provider_type: str,
    provider: MessageTransportProvider,
) -> None:
    """Register string provider type mapping."""
    normalized = provider_type.strip().lower()
    if normalized == "":
        raise ValueError("Provider type must not be empty")
    _PROVIDER_TYPE_REGISTRY[normalized] = provider


def register_timeline_endpoint_sender(
    *,
    provider: MessageTransportProvider,
    factory: Callable[[AsyncSession], TimelineEndpointSender],
) -> None:
    """Register endpoint-level timeline sender factory."""
    _TIMELINE_SENDER_REGISTRY[provider] = factory


def resolve_transport_provider(provider_type: str) -> MessageTransportProvider:
    """Resolve provider type string to transport provider enum."""
    normalized = provider_type.strip().lower()
    provider = _PROVIDER_TYPE_REGISTRY.get(normalized)
    if provider is not None:
        return provider
    raise ValueError(f"Unsupported provider type: {provider_type}")


def get_default_transport_provider() -> MessageTransportProvider:
    """Get default transport provider enum from internal selection logic."""
    return resolve_transport_provider(DEFAULT_PROVIDER_TYPE)


def create_timeline_endpoint_sender(
    db: AsyncSession,
    *,
    provider: MessageTransportProvider,
) -> TimelineEndpointSender:
    """Create endpoint sender by transport provider enum."""
    factory = _TIMELINE_SENDER_REGISTRY.get(provider)
    if factory is None:
        raise ValueError(f"No timeline sender registered for provider={provider.name}")
    return factory(db)


register_transport_provider_type(PROVIDER_TYPE_WEBSOCKET, MessageTransportProvider.WEBSOCKET)
register_timeline_endpoint_sender(
    provider=MessageTransportProvider.WEBSOCKET,
    factory=lambda _db: WebSocketTimelineSender(),
)
