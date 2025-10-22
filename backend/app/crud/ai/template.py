"""
AI Template CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI template management (info templates and profile templates).
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIInfoTemplate, AIProfileTemplate
from schemas.ai import (
    AIInfoTemplateCreate,
    AIInfoTemplateUpdate,
    AIProfileTemplateCreate,
    AIProfileTemplateUpdate,
)
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIInfoTemplate(CRUDBase[AIInfoTemplate, AIInfoTemplateCreate, AIInfoTemplateUpdate]):
    """AI Info Template CRUD operations with complex queries."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[AIInfoTemplate]:
        """
        Get info template by name.

        Args:
            db: Database session
            name: Template name

        Returns:
            Info template object or None if not found
        """
        try:
            result = await db.execute(select(AIInfoTemplate).where(AIInfoTemplate.name == name))
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("info_template_get_by_name_failed", error=str(e), name=name)
            return None

    async def get_available_templates(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AIInfoTemplate]:
        """
        Get available info templates.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available info templates
        """
        try:
            result = await db.execute(
                select(AIInfoTemplate)
                .where(AIInfoTemplate.status == 1)  # active
                .order_by(AIInfoTemplate.name)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("available_info_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("available_info_templates_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def get_reusable_templates(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AIInfoTemplate]:
        """
        Get reusable info templates.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of reusable info templates
        """
        try:
            result = await db.execute(
                select(AIInfoTemplate)
                .where(AIInfoTemplate.status == 1, AIInfoTemplate.is_reusable == True)  # active
                .order_by(AIInfoTemplate.name)
                .offset(skip)
                .limit(limit)
            )

            templates = result.scalars().all()

            logger.debug("reusable_info_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("reusable_info_templates_query_failed", error=str(e))
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

    async def get_profile_with_info(
        self, db: AsyncSession, *, template_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get profile template with associated info template.

        Args:
            db: Database session
            template_id: Profile template ID

        Returns:
            Dictionary containing templates, or None if not found
        """
        try:
            result = await db.execute(
                select(AIProfileTemplate, AIInfoTemplate)
                .join(AIInfoTemplate, AIProfileTemplate.info_id == AIInfoTemplate.id)
                .where(AIProfileTemplate.id == template_id)
            )

            row = result.first()
            if not row:
                logger.warning("profile_template_not_found", template_id=template_id)
                return None

            profile_template, info_template = row

            return {
                "profile_template": profile_template,
                "info_template": info_template,
            }

        except Exception as e:
            logger.error("profile_template_with_info_query_failed", error=str(e), template_id=template_id)
            raise RuntimeError(f"Failed to get profile template with info: {str(e)}")

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
        self, db: AsyncSession, *, profile_template_id: int, info_template_id: int
    ) -> Dict[str, bool]:
        """
        Check if templates are reusable.

        Args:
            db: Database session
            profile_template_id: Profile template ID
            info_template_id: Info template ID

        Returns:
            Dictionary with reusability flags
        """
        try:
            # Check profile template
            profile_result = await db.execute(
                select(AIProfileTemplate.is_reusable).where(AIProfileTemplate.id == profile_template_id)
            )
            profile_reusable = profile_result.scalar_one_or_none()

            # Check info template
            info_result = await db.execute(
                select(AIInfoTemplate.is_reusable).where(AIInfoTemplate.id == info_template_id)
            )
            info_reusable = info_result.scalar_one_or_none()

            return {
                "profile_reusable": bool(profile_reusable),
                "info_reusable": bool(info_reusable),
            }

        except Exception as e:
            logger.error(
                "template_reusability_check_failed",
                error=str(e),
                profile_template_id=profile_template_id,
                info_template_id=info_template_id,
            )
            # Default to not reusable for safety
            return {
                "profile_reusable": False,
                "info_reusable": False,
            }

    async def cleanup_single_use_templates(
        self, db: AsyncSession, *, profile_template_id: int, info_template_id: int
    ) -> None:
        """
        Clean up single-use templates after character creation.

        Args:
            db: Database session
            profile_template_id: Profile template ID
            info_template_id: Info template ID
        """
        try:
            # Check and delete profile template if not reusable
            profile_template = await self.get(db, id=profile_template_id)

            if profile_template and not profile_template.is_reusable:
                await self.remove(db, id=profile_template_id)
                logger.debug("single_use_profile_template_deleted", template_id=profile_template_id)

            # Check and delete info template if not reusable
            info_template = await ai_info_template.get(db, id=info_template_id)

            if info_template and not info_template.is_reusable:
                await ai_info_template.remove(db, id=info_template_id)
                logger.debug("single_use_info_template_deleted", template_id=info_template_id)

            await db.flush()

        except Exception as e:
            logger.error(
                "template_cleanup_failed",
                error=str(e),
                profile_template_id=profile_template_id,
                info_template_id=info_template_id,
            )
            # Non-fatal error: log but don't raise


ai_info_template = CRUDAIInfoTemplate(AIInfoTemplate)
ai_profile_template = CRUDAIProfileTemplate(AIProfileTemplate)
