"""
JWT token generation and validation utilities.
"""

import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.config import settings
from enums import DeviceType


def generate_jwt_token(
    user_id: int, qiao_id: str, device_type: DeviceType, session_id: Optional[int] = None
) -> str:
    """
    Generate a JWT token for user authentication.

    Args:
        user_id: Internal user ID
        qiao_id: User's qiao_id
        device_type: Device type enum
        session_id: Optional session/token record ID (will be set after token creation)

    Returns:
        JWT token string
    """
    from utils.snowflake import generate_snowflake_id

    # Get expiration time from system config (in seconds)
    # Default to 14 days if not configured
    expires_in = 1209600  # 14 days in seconds

    now = datetime.utcnow()
    exp = now + timedelta(seconds=expires_in)

    payload = {
        "sub": qiao_id,  # Subject: user qiao_id
        "user_id": user_id,  # Internal user ID
        "session_id": session_id or generate_snowflake_id(),  # Session record ID
        "device_type": device_type.value,  # Device type
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(exp.timestamp()),  # Expiration
    }

    # Get JWT secret and algorithm from settings
    secret = settings.JWT_SECRET_KEY
    algorithm = settings.JWT_ALGORITHM

    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict, or None if invalid
    """
    try:
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


def calculate_token_expiry() -> datetime:
    """
    Calculate token expiration time based on system config.

    Returns:
        Expiration datetime (UTC)
    """
    # Get expiration time from system config (in seconds)
    # Default to 14 days if not configured
    expires_in = 1209600  # 14 days in seconds

    return datetime.utcnow() + timedelta(seconds=expires_in)
