"""
Admin password utilities.
Uses the main project's security module for consistency.
"""

# Import from main project's security module to ensure consistency
from core.security import (
    verify_password as core_verify_password,
    get_password_hash as core_get_password_hash,
    generate_password as core_generate_password,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using main project's security module"""
    return core_verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using main project's security module"""
    return core_get_password_hash(password)


def generate_password(length: int = 12) -> str:
    """Generate a random password using main project's security module"""
    return core_generate_password(length)
