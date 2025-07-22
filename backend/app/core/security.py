from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional, Dict
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext

from utils.logging import get_logger
from .config import settings


logger = get_logger(__name__)

# Create a CryptContext instance, specifying the hashing algorithm
# Using bcrypt is a good, secure choice.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using the configured context.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: Union[str, Any], entity_id: Optional[str] = None, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a JWT access token with user ID and entity_id.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    if entity_id:
        to_encode["entity_id"] = entity_id

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token and extract payload.

    Args:
        token: JWT token string

    Returns:
        Token payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        logger.debug("jwt_token_expired")
        return None
    except JWTError:
        logger.debug("jwt_token_invalid")
        return None
    except Exception as e:
        logger.debug("jwt_token_decode_error", error=str(e))
        return None


def is_token_near_expiry(token: str, threshold_minutes: int = 60) -> bool:
    """
    Check if token is near expiry (MVP simple refresh strategy).

    Args:
        token: JWT token string
        threshold_minutes: Minutes before expiry to consider "near expiry"

    Returns:
        bool: True if token expires within threshold_minutes
    """
    try:
        payload = decode_access_token(token)
        if not payload or "exp" not in payload:
            return True  # Invalid token should be refreshed

        exp_timestamp = payload["exp"]
        current_timestamp = datetime.now(timezone.utc).timestamp()
        time_until_expiry = exp_timestamp - current_timestamp

        # Convert threshold to seconds
        threshold_seconds = threshold_minutes * 60

        return time_until_expiry <= threshold_seconds
    except Exception as e:
        logger.debug("token_expiry_check_error", error=str(e))
        return True  # On error, assume refresh needed


def refresh_token_if_needed(token: str, entity_id: str) -> Optional[str]:
    """
    Simple token refresh for MVP: create new token if current one is near expiry.

    Args:
        token: Current JWT token
        entity_id: User entity ID

    Returns:
        str: New token if refresh was needed, None if current token is still valid
    """
    try:
        if is_token_near_expiry(token):
            logger.info("token_refresh_triggered", entity_id=entity_id)
            new_token = create_access_token(subject=entity_id, entity_id=entity_id)
            return new_token
        return None
    except Exception as e:
        logger.error("token_refresh_error", entity_id=entity_id, error=str(e))
        return None
