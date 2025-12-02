"""
JWT token generation and validation utilities.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from core.config import get_settings
from enums import DeviceType
from utils.snowflake import generate_snowflake_id


def generate_jwt_token(
    user_id: int,
    qiao_id: str,
    device_type: DeviceType,
    expires_in_seconds: int,
    session_id: int | None = None,
) -> str:
    """
    Generate a JWT token for user authentication.

    Args:
        user_id: Internal user ID
        qiao_id: User's qiao_id
        device_type: Device type enum
        expires_in_seconds: Token lifetime in seconds
        session_id: Optional session/token record ID (will be set after token creation)

    Returns:
        JWT token string
    """

    now = datetime.now(UTC)
    exp = now + timedelta(seconds=expires_in_seconds)

    payload = {
        "sub": qiao_id,  # Subject: user qiao_id
        "user_id": user_id,  # Internal user ID
        "session_id": session_id or generate_snowflake_id(),  # Session record ID
        "device_type": device_type.value,  # Device type
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(exp.timestamp()),  # Expiration
    }

    # Get JWT secret and algorithm from settings
    settings = get_settings()
    secret = settings.JWT_SECRET_KEY
    algorithm = settings.JWT_ALGORITHM

    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_jwt_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict, or None if invalid
    """
    try:
        settings = get_settings()
        secret = settings.JWT_SECRET_KEY
        algorithm = settings.JWT_ALGORITHM

        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.InvalidTokenError:
        # Token is invalid
        return None


def calculate_token_expiry(expires_in_seconds: int) -> datetime:
    """Calculate token expiration timestamp based on provided duration."""

    return datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
