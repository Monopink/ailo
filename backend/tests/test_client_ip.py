"""Tests for trusted-proxy client IP resolution."""

import pytest
from starlette.requests import Request

from app.core.config import reset_settings_cache
from app.utils.client_ip import ClientIPResolutionError, get_client_ip


def _build_request(*, headers: list[tuple[bytes, bytes]], client: tuple[str, int]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/login",
        "headers": headers,
        "client": client,
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _configure_trusted_proxy_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLIENT_IP_MODE", "trusted_header")
    monkeypatch.setenv("CLIENT_IP_HEADER", "X-Client-IP")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["127.0.0.1/32"]')
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_get_client_ip_returns_header_value_for_trusted_proxy() -> None:
    request = _build_request(
        headers=[(b"x-client-ip", b"203.0.113.10")],
        client=("127.0.0.1", 12345),
    )

    assert get_client_ip(request) == "203.0.113.10"


def test_get_client_ip_rejects_missing_header() -> None:
    request = _build_request(headers=[], client=("127.0.0.1", 12345))

    with pytest.raises(ClientIPResolutionError) as exc_info:
        get_client_ip(request)

    assert exc_info.value.reason == "missing_client_ip_header"


def test_get_client_ip_rejects_untrusted_proxy() -> None:
    request = _build_request(
        headers=[(b"x-client-ip", b"203.0.113.10")],
        client=("198.51.100.5", 12345),
    )

    with pytest.raises(ClientIPResolutionError) as exc_info:
        get_client_ip(request)

    assert exc_info.value.reason == "untrusted_request_peer"


def test_get_client_ip_peer_mode_uses_request_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLIENT_IP_MODE", "peer")
    reset_settings_cache()
    request = _build_request(headers=[], client=("198.51.100.5", 12345))

    assert get_client_ip(request) == "198.51.100.5"
