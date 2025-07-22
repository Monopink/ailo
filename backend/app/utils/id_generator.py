"""
ID generation utilities for creating unique string IDs
"""

import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from utils.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


def generate_entity_id(length: int = 10) -> str:
    """
    Generate entity_id string with configurable prefix
    Format: {prefix}{length}-character random string
    Character set: lowercase letters + numbers, avoiding confusing characters
    """
    # Remove confusing characters: 0,o,1,l,i
    chars = "23456789abcdefghjkmnpqrstuvwxyz"  # 29 characters
    random_part = "".join(random.choices(chars, k=length))
    return f"{settings.ENTITY_ID_PREFIX}{random_part}"


def generate_template_id(length: int = 6) -> str:
    """
    Generate template_id string
    Format: 6-character random string
    Only needs to be unique within bot_templates table
    """
    chars = "23456789abcdefghjkmnpqrstuvwxyz"
    return "".join(random.choices(chars, k=length))


async def generate_unique_entity_id(session: AsyncSession, length: int = 10, max_retries: int = 10) -> str:
    """
    Generate globally unique entity_id across all tables

    Args:
        session: Database session
        length: Length of entity_id (default 10)
        max_retries: Maximum retry attempts

    Returns:
        str: Globally unique entity_id

    Raises:
        RuntimeError: If unable to generate unique ID after max attempts
    """
    # All tables that use entity_id
    tables_with_entity_id = ["users", "bots", "social_profiles", "template_mappings"]

    for attempt in range(max_retries):
        entity_id = generate_entity_id(length)

        # Check global uniqueness
        is_unique = True
        for table in tables_with_entity_id:
            result = await session.execute(
                text(f"SELECT 1 FROM {table} WHERE entity_id = :entity_id LIMIT 1"),
                {"entity_id": entity_id},
            )
            if result.scalar():
                is_unique = False
                break

        if is_unique:
            logger.debug(
                "unique_entity_id_generated", entity_id=entity_id, length=length, attempt=attempt + 1
            )
            return entity_id

    # If 10 digits not enough, expand to 12
    if length == 10:
        logger.warning("entity_id_10_digits_exhausted_expanding_to_12")
        return await generate_unique_entity_id(session, length=12, max_retries=max_retries)

    raise RuntimeError(f"Failed to generate unique entity_id after {max_retries} attempts")


async def generate_unique_template_id(session: AsyncSession, length: int = 6, max_retries: int = 10) -> str:
    """
    Generate unique template_id within bot_templates table

    Args:
        session: Database session
        length: Length of template_id (default 6)
        max_retries: Maximum retry attempts

    Returns:
        str: Unique template_id

    Raises:
        RuntimeError: If unable to generate unique ID after max attempts
    """
    for attempt in range(max_retries):
        template_id = generate_template_id(length)

        result = await session.execute(
            text("SELECT 1 FROM bot_templates WHERE template_id = :template_id LIMIT 1"),
            {"template_id": template_id},
        )

        if not result.scalar():
            logger.debug(
                "unique_template_id_generated", template_id=template_id, length=length, attempt=attempt + 1
            )
            return template_id

    # Expand length if needed
    if length == 6:
        logger.warning("template_id_6_digits_exhausted_expanding_to_8")
        return await generate_unique_template_id(session, length=8, max_retries=max_retries)

    raise RuntimeError(f"Failed to generate unique template_id after {max_retries} attempts")
