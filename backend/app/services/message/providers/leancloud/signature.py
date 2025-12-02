"""
LeanCloud signature generation service.

Implements HMAC-SHA1 signature algorithm for LeanCloud IM authentication.
Reference: https://docs.leancloud.cn/sdk/im/guide/senior/#%E7%AD%BE%E5%90%8D%E6%A0%BC%E5%BC%8F%E8%AF%B4%E6%98%8E
"""

import hashlib
import hmac
import secrets
import time
from typing import Any

from core.config import get_settings


def generate_nonce() -> str:
    """
    Generate a random nonce string.

    Returns:
        Random base64-encoded string (16 bytes)
    """
    # Generate 16 random bytes and encode as base64
    random_bytes = secrets.token_bytes(16)
    return secrets.token_urlsafe(16)


def get_timestamp_ms() -> int:
    """
    Get current UTC timestamp in milliseconds.

    Returns:
        Current UTC timestamp in milliseconds since Unix epoch
    """
    return int(time.time() * 1000)


def generate_signature(
    app_id: str, client_id: str, timestamp: int, nonce: str, master_key: str
) -> str:
    """
    Generate HMAC-SHA1 signature for LeanCloud IM login.

    Signature format: appid:clientid::timestamp:nonce
    Note: There are TWO colons between clientid and timestamp

    Args:
        app_id: LeanCloud application ID
        client_id: Client ID (user qiao_id)
        timestamp: UTC timestamp in milliseconds
        nonce: Random nonce string
        master_key: LeanCloud master key

    Returns:
        Hex-encoded HMAC-SHA1 signature string
    """
    # Construct message with TWO colons between clientid and timestamp
    message = f"{app_id}:{client_id}::{timestamp}:{nonce}"

    # Generate HMAC-SHA1 signature
    signature_bytes = hmac.new(
        master_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha1
    ).digest()

    # Convert to hex string
    signature_hex = signature_bytes.hex()

    return signature_hex


async def create_login_signature(app_id: str, client_id: str) -> dict[str, Any]:
    """
    Create a complete login signature package for LeanCloud IM.

    Args:
        app_id: LeanCloud application ID
        client_id: Client ID (user qiao_id)

    Returns:
        Dictionary containing:
        - signature: HMAC-SHA1 signature
        - timestamp: UTC timestamp in milliseconds
        - nonce: Random nonce string
    """
    # Generate timestamp and nonce
    timestamp = get_timestamp_ms()
    nonce = generate_nonce()

    # Get master key from environment
    master_key = get_settings().LEANCLOUD_MASTER_KEY

    # Generate signature
    signature = generate_signature(
        app_id=app_id, client_id=client_id, timestamp=timestamp, nonce=nonce, master_key=master_key
    )

    return {"signature": signature, "timestamp": timestamp, "nonce": nonce}
