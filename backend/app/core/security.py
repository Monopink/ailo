from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional, Dict
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import secrets
import string

from utils.logging import get_logger
from .config import settings


logger = get_logger(__name__)

# Create Argon2 password hasher with secure defaults
ph = PasswordHasher(
    time_cost=2,  # Number of iterations
    memory_cost=65536,  # Memory usage in KB (64MB)
    parallelism=1,  # Number of parallel threads
    hash_len=32,  # Hash output length
    salt_len=16,  # Salt length
)


def get_password_hash(password: str) -> str:
    """
    Hash a plain-text password using Argon2.
    """
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against an Argon2 hash.
    Handles all possible Argon2 verification errors gracefully.
    """
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        # Password does not match the hash - normal case
        return False
    except (VerificationError, InvalidHashError) as e:
        # Hash format invalid, parameter mismatch, or other verification errors
        # Log for debugging but return False to trigger normal error message
        logger.debug(
            "password_verification_error",
            error_type=type(e).__name__,
            error_message=str(e),
            hash_prefix=hashed_password[:20] if hashed_password else "empty",
        )
        return False
    except Exception as e:
        # Catch any other unexpected errors
        logger.warning(
            "unexpected_password_verification_error", error_type=type(e).__name__, error_message=str(e)
        )
        return False


def generate_password(length: int = 12) -> str:
    """
    Generate a cryptographically secure random password.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


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
    except InvalidTokenError:
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
