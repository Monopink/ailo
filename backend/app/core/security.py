"""Security utilities for authentication and password management."""

import secrets
import string
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to verify against

    Returns:
        bool: True if password matches, False otherwise

    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        str: The hashed password

    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_password(length: int = 12) -> str:
    """Generate a random password.

    Args:
        length: Length of the password to generate

    Returns:
        str: A randomly generated password

    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        subject: The subject (usually user ID) to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        str: The encoded JWT token

    """
    settings = get_settings()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, str | int] | None:
    """Decode and verify a JWT access token.

    Args:
        token: The JWT token to decode

    Returns:
        dict: The decoded payload if valid (contains 'sub' and 'exp'), None otherwise

    """
    settings = get_settings()
    try:
        payload: dict[str, str | int] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None


# Admin authentication is handled by Starlette-Admin session-based authentication
# No need for admin JWT tokens
