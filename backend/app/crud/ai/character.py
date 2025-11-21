"""
AI Character CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI character management.
"""

from typing import Any, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AICharacter
from schemas.ai import AICharacterCreate, AICharacterUpdate
from services.ai.usage_tracking import increment_usage_count, decrement_usage_count
from utils.logging import get_logger
from enums import AICharacterCreator, ContactType
from models.contact import Contact

logger = get_logger(__name__)


class CRUDAICharacter(CRUDBase[AICharacter, AICharacterCreate, AICharacterUpdate]):
    """AI Character CRUD operations with complex queries and usage tracking."""

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> Optional[AICharacter]:
        """
        Get character by qiao_id.

        Args:
            db: Database session
            qiao_id: Character's qiao_id

        Returns:
            Character object or None if not found
        """
        try:
            result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == qiao_id))
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("character_get_by_qiao_id_failed", error=str(e), qiao_id=qiao_id)
            raise RuntimeError(f"Failed to get character by qiao_id: {str(e)}")

    # Complex queries moved to services/ai/data layer for better separation of concerns

    async def get_user_characters(
        self, db: AsyncSession, *, user_qiao_id: str, skip: int = 0, limit: int = 100
    ) -> List[AICharacter]:
        """
        Get characters created by a specific user.

        Args:
            db: Database session
            user_qiao_id: User's qiao_id
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of characters
        """
        try:
            result = await db.execute(
                select(AICharacter)
                .join(Contact, Contact.contact_qiao_id == AICharacter.qiao_id)
                .where(
                    Contact.user_qiao_id == user_qiao_id,
                    Contact.contact_type == ContactType.AI,
                    Contact.is_deleted == 0,
                )
                .order_by(desc(AICharacter.created_at))
                .offset(skip)
                .limit(limit)
            )

            characters = list(result.scalars().all())

            logger.debug("user_characters_retrieved", user_qiao_id=user_qiao_id, count=len(characters))

            return characters

        except Exception as e:
            logger.error("user_characters_query_failed", error=str(e), user_qiao_id=user_qiao_id)
            # Non-fatal error: return empty list
            return []

    async def create(
        self, db: AsyncSession, *, obj_in: AICharacterCreate, commit: bool = True
    ) -> AICharacter:
        """
        Create a new AI character and update usage counts.

        Args:
            db: Database session
            obj_in: Character creation schema

        Returns:
            Created character object

        Raises:
            Exception: If creation or usage tracking fails
        """
        try:
            # Map schema fields to model fields to avoid invalid kwargs
            data = obj_in.model_dump()
            # placeholder_overrides -> prompt_variables
            if "placeholder_overrides" in data:
                data["prompt_variables"] = data.pop("placeholder_overrides")
            # Remove schema-only fields not present in model
            data.pop("position_mapping_coefficient", None)
            # Ensure created_by exists (DB requires non-null)
            data.setdefault("created_by", int(AICharacterCreator.USER))

            # Create character explicitly (bypass base create for field mapping)
            db_obj = AICharacter(**data)
            db.add(db_obj)
            if commit:
                await db.commit()
                await db.refresh(db_obj)
            else:
                # Inside outer transaction: flush to get PKs without closing transaction
                await db.flush()
            character = db_obj

            # Update usage counts for personality and style
            await increment_usage_count(db, "personality", character.personality_id)
            await increment_usage_count(db, "style", character.style_id)

            logger.info(
                "character_created_with_usage_tracking",
                character_id=character.id,
                personality_id=character.personality_id,
                style_id=character.style_id,
            )

            return character

        except Exception as e:
            logger.error("character_creation_failed", error=str(e))
            raise

    async def remove(self, db: AsyncSession, *, id: Any) -> Optional[AICharacter]:
        """
        Remove an AI character and update usage counts.

        Args:
            db: Database session
            id: Character ID

        Returns:
            Removed character object or None if not found

        Raises:
            Exception: If removal or usage tracking fails
        """
        try:
            # Get character first to access personality_id and style_id
            character = await self.get(db, id=id)

            if not character:
                logger.warning("character_not_found_for_removal", character_id=id)
                return None

            personality_id = character.personality_id
            style_id = character.style_id

            # Remove character using base class method
            removed_character = await super().remove(db, id=id)

            # Update usage counts for personality and style
            await decrement_usage_count(db, "personality", personality_id)
            await decrement_usage_count(db, "style", style_id)

            logger.info(
                "character_removed_with_usage_tracking",
                character_id=id,
                personality_id=personality_id,
                style_id=style_id,
            )

            return removed_character

        except Exception as e:
            logger.error("character_removal_failed", error=str(e), character_id=id)
            raise


ai_character = CRUDAICharacter(AICharacter)
