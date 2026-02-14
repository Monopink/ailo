"""Unified presence endpoint registration and renewal service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageEndpointScope, MessageTransportProvider
from app.models.message import MessageEndpoint


def _now_utc() -> datetime:
    return datetime.now(UTC)


async def upsert_websocket_presence_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    device_id: UUID,
    lease_ttl_seconds: int,
    client_kind: int | None = None,
) -> MessageEndpoint:
    """Create or renew WebSocket DEVICE-scope presence endpoint."""
    if lease_ttl_seconds <= 0:
        raise ValueError("ws_presence_lease_ttl_seconds must be positive")

    return await _upsert_presence_endpoint(
        db,
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        provider=MessageTransportProvider.WEBSOCKET,
        endpoint_scope=MessageEndpointScope.DEVICE,
        target_key=str(device_id),
        device_id=device_id,
        lease_expires_at=_now_utc() + timedelta(seconds=lease_ttl_seconds),
        client_kind=client_kind,
    )


async def upsert_leancloud_presence_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    client_id: str,
    lease_ttl_days: int,
    client_kind: int | None = None,
) -> MessageEndpoint:
    """Create or renew LeanCloud USER-scope presence endpoint."""
    if lease_ttl_days <= 0:
        raise ValueError("registration_lease_ttl_days must be positive")
    if not client_id:
        raise ValueError("client_id is required for LeanCloud presence")

    return await _upsert_presence_endpoint(
        db,
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        provider=MessageTransportProvider.LEANCLOUD,
        endpoint_scope=MessageEndpointScope.USER,
        target_key=client_id,
        device_id=None,
        lease_expires_at=_now_utc() + timedelta(days=lease_ttl_days),
        client_kind=client_kind,
    )


async def _upsert_presence_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    user_qiao_id: str,
    provider: MessageTransportProvider,
    endpoint_scope: MessageEndpointScope,
    target_key: str,
    device_id: UUID | None,
    lease_expires_at: datetime,
    client_kind: int | None,
) -> MessageEndpoint:
    now = _now_utc()

    existing = await _find_endpoint(
        db,
        user_id=user_id,
        provider=provider,
        endpoint_scope=endpoint_scope,
        target_key=target_key,
        device_id=device_id,
    )
    if existing is not None:
        _apply_presence_update(
            existing,
            user_qiao_id=user_qiao_id,
            provider=provider,
            endpoint_scope=endpoint_scope,
            target_key=target_key,
            device_id=device_id,
            client_kind=client_kind,
            lease_expires_at=lease_expires_at,
            now=now,
        )
        db.add(existing)
        await db.flush()
        return existing

    try:
        async with db.begin_nested():
            endpoint = MessageEndpoint(
                user_id=user_id,
                user_qiao_id=user_qiao_id,
                endpoint_scope=endpoint_scope,
                device_id=device_id,
                provider=provider,
                target_key=target_key,
                client_kind=client_kind,
                lease_expires_at=lease_expires_at,
                last_seen_at=now,
            )
            db.add(endpoint)
            await db.flush()
            return endpoint
    except IntegrityError:
        pass

    endpoint_after_conflict = await _find_endpoint(
        db,
        user_id=user_id,
        provider=provider,
        endpoint_scope=endpoint_scope,
        target_key=target_key,
        device_id=device_id,
    )
    if endpoint_after_conflict is None:
        raise ValueError("Failed to upsert presence endpoint")

    _apply_presence_update(
        endpoint_after_conflict,
        user_qiao_id=user_qiao_id,
        provider=provider,
        endpoint_scope=endpoint_scope,
        target_key=target_key,
        device_id=device_id,
        client_kind=client_kind,
        lease_expires_at=lease_expires_at,
        now=now,
    )
    db.add(endpoint_after_conflict)
    await db.flush()
    return endpoint_after_conflict


async def _find_endpoint(
    db: AsyncSession,
    *,
    user_id: int,
    provider: MessageTransportProvider,
    endpoint_scope: MessageEndpointScope,
    target_key: str,
    device_id: UUID | None,
) -> MessageEndpoint | None:
    query = select(MessageEndpoint).where(
        MessageEndpoint.user_id == user_id,
        MessageEndpoint.provider == provider,
        MessageEndpoint.endpoint_scope == endpoint_scope,
        MessageEndpoint.target_key == target_key,
    )
    if device_id is None:
        query = query.where(MessageEndpoint.device_id.is_(None))
    else:
        query = query.where(MessageEndpoint.device_id == device_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _apply_presence_update(
    endpoint: MessageEndpoint,
    *,
    user_qiao_id: str,
    provider: MessageTransportProvider,
    endpoint_scope: MessageEndpointScope,
    target_key: str,
    device_id: UUID | None,
    client_kind: int | None,
    lease_expires_at: datetime,
    now: datetime,
) -> None:
    endpoint.user_qiao_id = user_qiao_id
    endpoint.provider = provider
    endpoint.endpoint_scope = endpoint_scope
    endpoint.target_key = target_key
    endpoint.device_id = device_id
    endpoint.client_kind = client_kind
    endpoint.lease_expires_at = lease_expires_at
    endpoint.last_seen_at = now


__all__ = [
    "upsert_leancloud_presence_endpoint",
    "upsert_websocket_presence_endpoint",
]
