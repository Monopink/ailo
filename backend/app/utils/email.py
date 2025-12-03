"""
Email utility functions

Handles email validation and masking.
"""

import re

from app.utils.logging import get_logger

logger = get_logger(__name__)


def validate_email(email: str) -> bool:
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False

    # Basic email regex pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def mask_email(email: str) -> str:
    """
    Mask email address for display

    Format: first_letter + *** + @ + domain
    Example: user@example.com → u***@example.com

    Args:
        email: Email address to mask

    Returns:
        Masked email address
    """
    if not email or "@" not in email:
        return email

    try:
        local, domain = email.split("@", 1)
        if len(local) > 0:
            # Keep first letter, mask the rest
            masked_local = local[0] + "***"
            return f"{masked_local}@{domain}"
        return email
    except Exception as e:
        logger.error(f"Failed to mask email: {e}")
        return email
