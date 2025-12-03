"""
AI template/persona CRUD operations.

This module provides both standard CRUD operations and helper queries
for template and persona management.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.ai import AIPersona, AITemplate
from app.schemas.ai import AIPersonaCreate, AIPersonaUpdate, AITemplateCreate, AITemplateUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAITemplate(CRUDBase[AITemplate, AITemplateCreate, AITemplateUpdate]):
    """AI Template CRUD operations with complex queries."""

    async def get_available_templates(
        self,
        db: AsyncSession,
        *,
        type_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[AITemplate]:
        """
        Get available templates.

        Args:
            db: Database session
            type_id: Optional AI type filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available templates
        """
        try:
            stmt = select(AITemplate).where(AITemplate.status == 1)  # active
            if type_id is not None:
                stmt = stmt.where(AITemplate.type_id == type_id)
            stmt = stmt.order_by(AITemplate.display_name).offset(skip).limit(limit)

            result = await db.execute(stmt)

            templates = result.scalars().all()

            logger.debug("available_ai_templates_retrieved", count=len(templates))

            return templates

        except Exception as e:
            logger.error("available_ai_templates_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def get_active_template_for_type(
        self, db: AsyncSession, type_id: int
    ) -> AITemplate | None:
        """
        Pick the highest priority template for the given template type.
        """
        try:
            stmt = (
                select(AITemplate)
                .where(
                    AITemplate.type_id == type_id,
                    AITemplate.status == 1,
                )
                .order_by(
                    AITemplate.priority.asc(),
                    AITemplate.is_reusable.asc(),  # single-use first
                    AITemplate.id.asc(),
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            template = result.scalar_one_or_none()
            if not template:
                logger.debug(
                    "no_template_for_type",
                    type_id=type_id,
                )
            return template
        except Exception as exc:
            logger.error(
                "template_selection_failed",
                error=str(exc),
                type_id=type_id,
            )
            return None


class CRUDAIPersona(CRUDBase[AIPersona, AIPersonaCreate, AIPersonaUpdate]):
    """AI persona CRUD operations with complex queries."""

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> AIPersona | None:
        try:
            result = await db.execute(select(self.model).where(self.model.qiao_id == qiao_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("persona_get_by_qiao_id_failed", error=str(e), qiao_id=qiao_id)
            return None

    # Legacy helper methods removed; persona inventory is now managed via services.


ai_template = CRUDAITemplate(AITemplate)
ai_persona = CRUDAIPersona(AIPersona)
