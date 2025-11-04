"""
AI Template CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI template management (character templates and profile templates).
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AICharacterTemplate, AIProfileTemplate
from schemas.ai import (
    AICharacterTemplateCreate,
    AICharacterTemplateUpdate,
    AIProfileTemplateCreate,
    AIProfileTemplateUpdate,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAICharacterTemplate(
    CRUDBase[AICharacterTemplate, AICharacterTemplateCreate, AICharacterTemplateUpdate]
):
    """AI Character Template CRUD operations with complex queries."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[AICharacterTemplate]:
        """
        Get character template by name.

        Args:
            db: Database session
            name: Template name

        Returns:
            Character template object or None if not found
        """
        try:
            result = await db.execute(
                select(AICharacterTemplate).where(AICharacterTemplate.name == name)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("character_template_get_by_name_failed", error=str(e), name=name)
            return None

    async def get_available_templates(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AICharacterTemplate]:
        """
        Get available character templates.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available character templates
        """
        try:
            result = await db.execute(
                select(AICharacterTemplate)
                .where(AICharacterTemplate.status == 1)  # active
                .order_by(AICharacterTemplate.name)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("available_character_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("available_character_templates_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def get_reusable_templates(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AICharacterTemplate]:
        """
        Get reusable character templates.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of reusable character templates
        """
        try:
            result = await db.execute(
                select(AICharacterTemplate)
                .where(
                    AICharacterTemplate.status == 1,
                    AICharacterTemplate.is_reusable == True,
                )  # active
                .order_by(AICharacterTemplate.name)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("reusable_character_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("reusable_character_templates_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []


class CRUDAIProfileTemplate(CRUDBase[AIProfileTemplate, AIProfileTemplateCreate, AIProfileTemplateUpdate]):
    """AI Profile Template CRUD operations with complex queries."""

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> Optional[AIProfileTemplate]:
        """
        Get profile template by qiao_id.

        Args:
            db: Database session
            qiao_id: Template qiao_id

        Returns:
            Profile template object or None if not found
        """
        try:
            result = await db.execute(select(self.model).where(self.model.qiao_id == qiao_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("profile_template_get_by_qiao_id_failed", error=str(e), qiao_id=qiao_id)
            return None

    async def get_profile_with_character_template(
        self, db: AsyncSession, *, template_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get profile template with associated character template.

        Args:
            db: Database session
            template_id: Profile template ID

        Returns:
            Dictionary containing templates, or None if not found
        """
        try:
            result = await db.execute(
                select(AIProfileTemplate, AICharacterTemplate)
                .join(
                    AICharacterTemplate,
                    AIProfileTemplate.character_template_id == AICharacterTemplate.id,
                )
                .where(AIProfileTemplate.id == template_id)
            )

            row = result.first()
            if not row:
                logger.warning("profile_template_not_found", template_id=template_id)
                return None

            profile_template, character_template = row

            return {
                "profile_template": profile_template,
                "character_template": character_template,
            }

        except Exception as e:
            logger.error(
                "profile_template_with_character_template_query_failed",
                error=str(e),
                template_id=template_id,
            )
            raise RuntimeError(
                f"Failed to get profile template with character template: {str(e)}"
            )

    async def get_by_category(
        self, db: AsyncSession, *, category: str, skip: int = 0, limit: int = 100
    ) -> List[AIProfileTemplate]:
        """
        Get profile templates by category.

        Args:
            db: Database session
            category: Template category
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of profile templates in the category
        """
        try:
            result = await db.execute(
                select(AIProfileTemplate)
                .where(AIProfileTemplate.category == category)
                .order_by(AIProfileTemplate.nickname)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("profile_templates_by_category_retrieved", category=category, count=len(templates))

            return templates

        except Exception as e:
            logger.error("profile_templates_by_category_query_failed", error=str(e), category=category)
            # Non-fatal error: return empty list
            return []

    async def get_available_templates(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AIProfileTemplate]:
        """
        Get available profile templates.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available profile templates
        """
        try:
            result = await db.execute(
                select(AIProfileTemplate)
                .where(AIProfileTemplate.status == 1)  # active
                .order_by(AIProfileTemplate.nickname)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("available_profile_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("available_profile_templates_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def check_template_reusability(
        self, db: AsyncSession, *, profile_template_id: int, character_template_id: int
    ) -> Dict[str, bool]:
        """
        Check if templates are reusable.

        Args:
            db: Database session
            profile_template_id: Profile template ID
            character_template_id: Character template ID

        Returns:
            Dictionary with reusability flags
        """
        try:
            # Check profile template
            profile_result = await db.execute(
                select(AIProfileTemplate.is_reusable).where(AIProfileTemplate.id == profile_template_id)
            )
            profile_reusable = profile_result.scalar_one_or_none()

            # Check character template
            character_result = await db.execute(
                select(AICharacterTemplate.is_reusable).where(
                    AICharacterTemplate.id == character_template_id
                )
            )
            character_reusable = character_result.scalar_one_or_none()

            return {
                "profile_reusable": bool(profile_reusable),
                "character_template_reusable": bool(character_reusable),
            }

        except Exception as e:
            logger.error(
                "template_reusability_check_failed",
                error=str(e),
                profile_template_id=profile_template_id,
                character_template_id=character_template_id,
            )
            # Default to not reusable for safety
            return {
                "profile_reusable": False,
                "character_template_reusable": False,
            }

    async def cleanup_single_use_templates(
        self, db: AsyncSession, *, profile_template_id: int, character_template_id: int
    ) -> None:
        """
        Clean up single-use templates after character creation.

        Args:
            db: Database session
            profile_template_id: Profile template ID
            character_template_id: Character template ID
        """
        try:
            # Check and delete profile template if not reusable
            profile_template = await self.get(db, id=profile_template_id)

            if profile_template and not profile_template.is_reusable:
                await self.remove(db, id=profile_template_id)
                logger.debug("single_use_profile_template_deleted", template_id=profile_template_id)

            # Check and delete character template if not reusable
            character_template = await ai_character_template.get(
                db, id=character_template_id
            )

            if character_template and not character_template.is_reusable:
                await ai_character_template.remove(db, id=character_template_id)
                logger.debug(
                    "single_use_character_template_deleted", template_id=character_template_id
                )

            await db.flush()

        except Exception as e:
            logger.error(
                "template_cleanup_failed",
                error=str(e),
                profile_template_id=profile_template_id,
                character_template_id=character_template_id,
            )
            # Non-fatal error: log but don't raise


ai_character_template = CRUDAICharacterTemplate(AICharacterTemplate)
ai_profile_template = CRUDAIProfileTemplate(AIProfileTemplate)
