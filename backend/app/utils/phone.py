"""Phone number utility functions.

Handles phone number normalization, validation, and masking.
"""

import re

from app.utils.logging import get_logger

logger = get_logger(__name__)

CHINA_LOCAL_LENGTH = 11
CHINA_E164_LENGTH = 14
NORTH_AMERICA_E164_LENGTH = 12
MIN_NUMBER_LENGTH_FOR_MASK = 5
MASK_BODY = "******"


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format.

    Handles various input formats:
        - "+8613800138000" → "+8613800138000"
        - "13800138000" → "+8613800138000"
        - "+86 138 0013 8000" → "+8613800138000"
        - "86-138-0013-8000" → "+8613800138000"

    Args:
        phone: Phone number in various formats

    Returns:
        Normalized phone number in E.164 format

    Raises:
        ValueError: If phone number format is invalid

    """
    if not phone:
        logger.error("Empty phone number")
        raise ValueError("Phone number cannot be empty")

    # Remove spaces, dashes, parentheses
    phone = re.sub(r"[\s\-\(\)]", "", phone)

    # Add + if not present
    if not phone.startswith("+"):
        if phone.startswith("86"):
            phone = "+" + phone
        elif phone.startswith("1") and len(phone) == CHINA_LOCAL_LENGTH:
            # China mobile number without country code
            phone = "+86" + phone
        else:
            logger.error(f"Invalid phone number format: {phone}")
            raise ValueError(f"Invalid phone number format: {phone}")

    # Validate E.164 format
    if not re.match(r"^\+[1-9]\d{1,14}$", phone):
        logger.error(f"Phone number does not match E.164 format: {phone}")
        raise ValueError(f"Invalid phone number format: {phone}")

    return phone


def is_china_phone(phone: str) -> bool:
    """Check if phone number is China mainland phone.

    Args:
        phone: Phone number in E.164 format

    Returns:
        True if China phone, False otherwise

    """
    return phone.startswith("+86")


def mask_phone(phone: str) -> str:
    """Mask phone number for display.

    Format: +[country_code] [first_3_digits]******[last_2_digits]
    Example: +8613800138000 → +86 138******00

    Args:
        phone: Phone number in E.164 format (e.g., "+8613800138000")

    Returns:
        Masked phone number (e.g., "+86 138******00")

    """
    if not phone or not phone.startswith("+"):
        return phone

    if phone.startswith("+86") and len(phone) == CHINA_E164_LENGTH:
        return f"+86 {phone[3:6]}{MASK_BODY}{phone[-2:]}"
    if phone.startswith("+1") and len(phone) == NORTH_AMERICA_E164_LENGTH:
        return f"+1 {phone[2:5]}{MASK_BODY}{phone[-2:]}"

    match = re.match(r"^(\+\d{1,3})(\d{3,})$", phone)
    if match:
        country_code = match.group(1)
        number = match.group(2)
        if len(number) >= MIN_NUMBER_LENGTH_FOR_MASK:
            return f"{country_code} {number[:3]}{MASK_BODY}{number[-2:]}"

    return phone
