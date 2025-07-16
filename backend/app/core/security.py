from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional

from jose import jwt
from passlib.context import CryptContext

from .config import settings

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
