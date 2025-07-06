import yaml
import os
from typing import Optional, Dict, Any
from ..utils.logging import get_logger

logger = get_logger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.yaml")


def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.debug("config_loaded", file=CONFIG_FILE, keys=list(config.keys()))
            return config
        except Exception as e:
            logger.error("config_load_failed", file=CONFIG_FILE, error=str(e))
            return {}
    else:
        logger.info("config_file_not_found", file=CONFIG_FILE)
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.debug("config_saved", file=CONFIG_FILE)

    except Exception as e:
        logger.error("config_save_failed", file=CONFIG_FILE, error=str(e), exc_info=True)
        raise


def get_unified_conversation_id() -> str:
    """
    Get unified system conversation ID.

    Returns:
        str: The conversation ID

    Raises:
        ValueError: If conversation ID is not configured and cannot be generated
    """
    config = load_config()
    conversation_id = config.get("leancloud", {}).get("unified_conversation_id")

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
    """Save unified conversation ID to config file."""
    if not conversation_id:
        raise ValueError("conversation_id cannot be empty")

    config = load_config()

    if "leancloud" not in config:
        config["leancloud"] = {}

    config["leancloud"]["unified_conversation_id"] = conversation_id
    save_config(config)

    logger.info("unified_conversation_id_saved", conversation_id=conversation_id)


def is_conversation_configured() -> bool:
    """Check if unified conversation ID is configured."""
    config = load_config()
    return bool(config.get("leancloud", {}).get("unified_conversation_id"))


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
