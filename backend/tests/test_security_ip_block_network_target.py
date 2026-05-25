"""Tests for network-based security IP block handling."""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.security.enforcement import InvalidClientIPError, is_ip_blocked
from app.services.security.ip_network_target import (
    normalize_block_target,
    normalize_client_ip,
    normalize_stored_network,
)


def test_normalize_block_target_single_ip_ipv4() -> None:
    normalized = normalize_block_target("203.0.113.7")
    assert normalized.target_network == "203.0.113.7/32"
    assert normalized.target_type == "single_ip"
    assert normalized.display_target == "203.0.113.7"


def test_normalize_block_target_cidr_ipv4_with_host_bits() -> None:
    normalized = normalize_block_target("203.0.113.23/24")
    assert normalized.target_network == "203.0.113.0/24"
    assert normalized.target_type == "cidr"
    assert normalized.display_target == "203.0.113.0/24"


def test_normalize_block_target_single_ip_ipv6() -> None:
    normalized = normalize_block_target("2001:db8::1")
    assert normalized.target_network == "2001:db8::1/128"
    assert normalized.target_type == "single_ip"
    assert normalized.display_target == "2001:db8::1"


def test_normalize_stored_network_prefers_single_ip_display() -> None:
    normalized = normalize_stored_network("203.0.113.7/32")
    assert normalized.target_type == "single_ip"
    assert normalized.display_target == "203.0.113.7"


def test_normalize_client_ip_invalid_returns_none() -> None:
    assert normalize_client_ip("not-an-ip") is None


@pytest.mark.asyncio
async def test_is_ip_blocked_fail_closed_when_query_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise_query_error(*_: object, **__: object) -> bool:
        raise SQLAlchemyError("forced query failure")

    monkeypatch.setattr(
        "app.services.security.enforcement.has_active_block_for_ip",
        _raise_query_error,
    )

    assert await is_ip_blocked(cast(AsyncSession, object()), "203.0.113.7") is True


@pytest.mark.asyncio
async def test_is_ip_blocked_raises_on_invalid_ip() -> None:
    with pytest.raises(InvalidClientIPError):
        await is_ip_blocked(cast(AsyncSession, object()), "not-an-ip")
