"""IP/CIDR normalization helpers for security block services."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

IPV4_VERSION = 4
IPV4_HOST_PREFIX = 32
IPV6_HOST_PREFIX = 128


@dataclass(slots=True, frozen=True)
class NormalizedNetworkTarget:
    """Canonical network target used by block storage and APIs."""

    target_network: str
    target_type: str
    display_target: str


def normalize_client_ip(raw_ip: str) -> str | None:
    """Normalize client IP text to compressed form."""
    candidate = raw_ip.strip()
    if candidate == "":
        return None
    try:
        return ipaddress.ip_address(candidate).compressed
    except ValueError:
        return None


def normalize_block_target(target: str) -> NormalizedNetworkTarget:
    """Normalize input target to canonical CIDR network representation."""
    raw_target = target.strip()
    if raw_target == "":
        raise ValueError("target_required")

    if "/" in raw_target:
        try:
            network = ipaddress.ip_network(raw_target, strict=False)
        except ValueError as exc:
            raise ValueError("target_invalid_cidr") from exc
        max_prefix = IPV4_HOST_PREFIX if network.version == IPV4_VERSION else IPV6_HOST_PREFIX
        if network.prefixlen == max_prefix:
            return NormalizedNetworkTarget(
                target_network=f"{network.network_address.compressed}/{network.prefixlen}",
                target_type="single_ip",
                display_target=network.network_address.compressed,
            )
        return NormalizedNetworkTarget(
            target_network=f"{network.network_address.compressed}/{network.prefixlen}",
            target_type="cidr",
            display_target=f"{network.network_address.compressed}/{network.prefixlen}",
        )

    try:
        parsed_ip = ipaddress.ip_address(raw_target)
    except ValueError as exc:
        raise ValueError("target_invalid_ip") from exc
    host_prefix = IPV4_HOST_PREFIX if parsed_ip.version == IPV4_VERSION else IPV6_HOST_PREFIX
    return NormalizedNetworkTarget(
        target_network=f"{parsed_ip.compressed}/{host_prefix}",
        target_type="single_ip",
        display_target=parsed_ip.compressed,
    )


def normalize_stored_network(target_network: str) -> NormalizedNetworkTarget:
    """Normalize persisted CIDR text for response serialization."""
    try:
        network = ipaddress.ip_network(target_network, strict=False)
    except ValueError as exc:
        raise ValueError("target_invalid_cidr") from exc
    max_prefix = IPV4_HOST_PREFIX if network.version == IPV4_VERSION else IPV6_HOST_PREFIX
    normalized_network = f"{network.network_address.compressed}/{network.prefixlen}"
    if network.prefixlen == max_prefix:
        return NormalizedNetworkTarget(
            target_network=normalized_network,
            target_type="single_ip",
            display_target=network.network_address.compressed,
        )
    return NormalizedNetworkTarget(
        target_network=normalized_network,
        target_type="cidr",
        display_target=normalized_network,
    )
