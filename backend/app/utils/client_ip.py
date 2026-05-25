"""Client IP resolution utilities for trusted reverse-proxy deployments."""

from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network

from starlette.requests import HTTPConnection

from app.core.config import get_settings

_REQUEST_STATE_CLIENT_IP_KEY = "resolved_client_ip"
IPAddress = IPv4Address | IPv6Address
IPNetwork = IPv4Network | IPv6Network


class ClientIPResolutionError(ValueError):
    """Raised when client IP cannot be resolved from a trusted proxy context."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


@lru_cache
def _trusted_proxy_networks(cidr_values: tuple[str, ...]) -> tuple[IPNetwork, ...]:
    return tuple(ip_network(value, strict=False) for value in cidr_values)


def get_client_ip(connection: HTTPConnection) -> str:
    """Return normalized client IP from trusted proxy header."""
    cached_ip = getattr(connection.state, _REQUEST_STATE_CLIENT_IP_KEY, None)
    if isinstance(cached_ip, str) and cached_ip:
        return cached_ip

    settings = get_settings()
    peer_host = connection.client.host if connection.client else ""
    if not peer_host:
        raise ClientIPResolutionError("missing_request_peer", "Request peer IP is missing")

    try:
        peer_ip: IPAddress = ip_address(peer_host.strip())
    except ValueError as exc:
        raise ClientIPResolutionError("invalid_request_peer", "Request peer IP is invalid") from exc

    if settings.CLIENT_IP_MODE == "peer":
        normalized_peer_ip = peer_ip.compressed
        setattr(connection.state, _REQUEST_STATE_CLIENT_IP_KEY, normalized_peer_ip)
        return normalized_peer_ip

    trusted_networks: tuple[IPNetwork, ...] = _trusted_proxy_networks(
        tuple(settings.TRUSTED_PROXY_CIDRS)
    )
    if not any(peer_ip in network for network in trusted_networks):
        raise ClientIPResolutionError(
            "untrusted_request_peer",
            "Request source is not in TRUSTED_PROXY_CIDRS",
        )

    raw_client_ip = connection.headers.get(settings.CLIENT_IP_HEADER, "").strip()
    if not raw_client_ip:
        raise ClientIPResolutionError("missing_client_ip_header", "Client IP header is missing")
    if "," in raw_client_ip:
        raise ClientIPResolutionError(
            "invalid_client_ip_header", "Client IP header must contain one IP"
        )

    try:
        normalized_client_ip = ip_address(raw_client_ip).compressed
    except ValueError as exc:
        raise ClientIPResolutionError(
            "invalid_client_ip_header",
            "Client IP header is not a valid IP address",
        ) from exc

    setattr(connection.state, _REQUEST_STATE_CLIENT_IP_KEY, normalized_client_ip)
    return normalized_client_ip
