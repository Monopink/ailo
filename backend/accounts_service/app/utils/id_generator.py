"""
ID generation utilities for creating unique string entity IDs
"""

import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.utils.logging import get_logger
from app.core.config import settings

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


async def generate_unique_entity_id(session: AsyncSession, length: int = 10, max_retries: int = 10) -> str:
    """
    Generate globally unique entity_id
    Checks all tables that use entity_id

    Args:
        session: Database session
        length: Length of entity_id (default 10)
        max_retries: Maximum retry attempts

    Returns:
        str: A unique entity_id string
    """
    # All tables that use entity_id
    tables_with_entity_id = [
        "users",
        # Add other tables as needed when they're created
    ]

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
