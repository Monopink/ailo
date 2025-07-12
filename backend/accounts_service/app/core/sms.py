import random
import time
from typing import Dict
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Mock SMS code storage, in production this should be replaced with Redis or a database.
# Format: { "phone_number": {"code": "123456", "timestamp": 1678886400} }
sms_code_storage: Dict[str, Dict] = {}

# Code expiration time in seconds
CODE_EXPIRATION_SECONDS = 300  # 5 minutes


def generate_sms_code() -> str:
    """Generates a 6-digit SMS verification code."""
    return str(random.randint(100000, 999999))


def send_sms_code(phone: str) -> str:
    """
    Generates and "sends" an SMS verification code.
    In this mock implementation, we only generate the code, print it to the console, and store it.
    """
    code = generate_sms_code()
    sms_code_storage[phone] = {"code": code, "timestamp": time.time()}
    logger.info("sms_code_generated", phone=phone, code=code, note="Mock SMS sending")  # Mock sending
    return code


def verify_sms_code(phone: str, code: str) -> bool:
    """
    Verifies the SMS code.
    Checks if the code exists, matches, and is within its validity period.
    """
    if phone not in sms_code_storage:
        return False

    stored_data = sms_code_storage[phone]

    # Check if the code has expired
    if time.time() - stored_data["timestamp"] > CODE_EXPIRATION_SECONDS:
        # Clear the expired code
        del sms_code_storage[phone]
        return False

    # Check if the code matches
    if stored_data["code"] == code:
        # Delete the code immediately after successful verification to prevent reuse
        del sms_code_storage[phone]
        return True

    return False
