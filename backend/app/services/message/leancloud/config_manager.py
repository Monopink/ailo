import os
from typing import Optional
from utils.logging import get_logger

logger = get_logger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "unified_conversation_id.txt")


def _read_conversation_id() -> str:
    """Read conversation ID from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                conversation_id = f.read().strip()
            logger.debug("conversation_id_loaded", file=CONFIG_FILE, conversation_id=conversation_id)
            return conversation_id
        except Exception as e:
            logger.error("conversation_id_load_failed", file=CONFIG_FILE, error=str(e))
            return ""
    else:
        logger.info("conversation_id_file_not_found", file=CONFIG_FILE)
        return ""


def _write_conversation_id(conversation_id: str) -> None:
    """Write conversation ID to file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(conversation_id)

        logger.debug("conversation_id_saved", file=CONFIG_FILE, conversation_id=conversation_id)

    except Exception as e:
        logger.error("conversation_id_save_failed", file=CONFIG_FILE, error=str(e), exc_info=True)
        raise


def get_unified_conversation_id() -> str:
    """
    Get unified system conversation ID.

    Returns:
        str: The conversation ID

    Raises:
        ValueError: If conversation ID is not configured and cannot be generated
    """
    conversation_id = _read_conversation_id()

    if not conversation_id:
        logger.warning("unified_conversation_id_not_found_attempting_regeneration")
        # Attempt to regenerate
        conversation_id = regenerate_conversation_id()

    if not conversation_id:
        raise ValueError(
            "Failed to get or generate unified conversation ID. "
            "Please check LeanCloud credentials and network connectivity."
        )

    return conversation_id


def set_unified_conversation_id(conversation_id: str) -> None:
    """Save unified conversation ID to file."""
    if not conversation_id:
        raise ValueError("conversation_id cannot be empty")

    _write_conversation_id(conversation_id)
    logger.info("unified_conversation_id_saved", conversation_id=conversation_id)


def is_conversation_configured() -> bool:
    """Check if unified conversation ID is configured."""
    conversation_id = _read_conversation_id()
    return bool(conversation_id)


def regenerate_conversation_id() -> Optional[str]:
    """Attempt to regenerate conversation ID."""
    try:
        from .conversation_auto_setup import create_system_conversation
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            conversation_id = loop.run_until_complete(create_system_conversation())
            if conversation_id:
                set_unified_conversation_id(conversation_id)
            return conversation_id
        finally:
            loop.close()

    except Exception as e:
        logger.error("conversation_regeneration_failed", error=str(e), exc_info=True)
        return None
