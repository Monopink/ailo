from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.bot_template import BotTemplate
from models.template_mapping import TemplateMapping
from models.bot import Bot
from utils.logging import get_logger
from .base import BaseRepository

logger = get_logger(__name__)


class TemplateRepository:
    """Repository for template and bot creation operations"""

    def __init__(self):
        self.template_repo = BaseRepository(BotTemplate)
        self.mapping_repo = BaseRepository(TemplateMapping)
        self.bot_repo = BaseRepository(Bot)

    async def get_available_templates(
        self, session: AsyncSession, template_status: str = "active"
    ) -> List[BotTemplate]:
        """
        Get available bot templates

        Args:
            session: Database session
            template_status: Template status filter

        Returns:
            List of available BotTemplate instances
        """
        try:
            result = await session.execute(
                select(BotTemplate).where(
                    and_(
                        BotTemplate.template_status == template_status,
                        func.coalesce(BotTemplate.remaining_uses, -1) != 0,  # Not exhausted
                    )
                )
            )
            return result.scalars().all()

        except Exception as e:
            logger.error("get_available_templates_error", error=str(e))
            raise

    async def get_template_by_id(self, session: AsyncSession, template_id: str) -> Optional[BotTemplate]:
        """
        Get bot template by template ID

        Args:
            session: Database session
            template_id: Template ID

        Returns:
            BotTemplate instance or None
        """
        try:
            result = await session.execute(
                select(BotTemplate).where(BotTemplate.template_id == template_id)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("get_template_by_id_error", error=str(e), template_id=template_id)
            raise

    async def decrease_template_usage(self, session: AsyncSession, template: BotTemplate) -> None:
        """
        Decrease template remaining uses

        Args:
            session: Database session
            template: BotTemplate instance to update
        """
        try:
            if template.remaining_uses is not None and template.remaining_uses > 0:
                template.remaining_uses -= 1
                # Mark as exhausted if reaches 0
                if template.remaining_uses == 0:
                    template.template_status = "exhausted"

            logger.debug(
                "template_usage_decreased",
                template_id=template.template_id,
                remaining_uses=template.remaining_uses,
                status=template.template_status,
            )

        except Exception as e:
            logger.error("decrease_template_usage_error", error=str(e), template_id=template.template_id)
            raise

    async def get_template_mappings_by_user(
        self, session: AsyncSession, user_entity_id: str, template_ids: List[str]
    ) -> Dict[str, TemplateMapping]:
        """
        Get template mappings for user and template IDs

        Args:
            session: Database session
            user_entity_id: User's entity ID
            template_ids: List of template IDs to query

        Returns:
            Dictionary mapping template_id to TemplateMapping instance
        """
        try:
            result = await session.execute(
                select(TemplateMapping).where(
                    and_(
                        TemplateMapping.user_entity_id == user_entity_id,
                        TemplateMapping.template_id.in_(template_ids),
                    )
                )
            )
            mappings = result.scalars().all()
            return {mapping.template_id: mapping for mapping in mappings}

        except Exception as e:
            logger.error("get_template_mappings_by_user_error", error=str(e), user_entity_id=user_entity_id)
            raise

    async def update_template_mapping_search_time(
        self, session: AsyncSession, mapping: TemplateMapping
    ) -> None:
        """
        Update template mapping last search time and reactivate if needed

        Args:
            session: Database session
            mapping: TemplateMapping instance to update
        """
        try:
            mapping.last_search_time = datetime.now()
            if mapping.status == "inactive":
                mapping.status = "active"

            logger.info(
                "template_mapping_search_time_updated",
                entity_id=mapping.entity_id,
                template_id=mapping.template_id,
            )

        except Exception as e:
            logger.error(
                "update_template_mapping_search_time_error",
                error=str(e),
                entity_id=mapping.entity_id,
            )
            raise

    async def create_template_mapping(
        self, session: AsyncSession, entity_id: str, user_entity_id: str, template_id: str
    ) -> TemplateMapping:
        """
        Create new template mapping

        Args:
            session: Database session
            entity_id: Unique entity ID for this mapping
            user_entity_id: User's entity ID
            template_id: Template ID

        Returns:
            Created TemplateMapping instance
        """
        try:
            new_mapping = TemplateMapping(
                entity_id=entity_id,
                user_entity_id=user_entity_id,
                template_id=template_id,
                last_search_time=datetime.now(),
                status="active",
            )
            session.add(new_mapping)
            # Note: Don't commit here, let the calling service handle transaction

            logger.info(
                "template_mapping_created",
                entity_id=entity_id,
                user_entity_id=user_entity_id,
                template_id=template_id,
            )
            return new_mapping

        except Exception as e:
            logger.error(
                "create_template_mapping_error",
                error=str(e),
                entity_id=entity_id,
                user_entity_id=user_entity_id,
                template_id=template_id,
            )
            raise

    async def get_template_mapping_by_entity_id(
        self, session: AsyncSession, user_entity_id: str, entity_id: str
    ) -> Optional[TemplateMapping]:
        """
        Get template mapping by entity ID

        Args:
            session: Database session
            user_entity_id: User's entity ID
            entity_id: Entity ID

        Returns:
            TemplateMapping instance or None
        """
        try:
            result = await session.execute(
                select(TemplateMapping).where(
                    and_(
                        TemplateMapping.entity_id == entity_id,
                        TemplateMapping.user_entity_id == user_entity_id,
                        TemplateMapping.status == "active",
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                "get_template_mapping_by_entity_id_error",
                error=str(e),
                user_entity_id=user_entity_id,
                entity_id=entity_id,
            )
            raise

    async def create_bot_from_template(
        self, session: AsyncSession, template: BotTemplate, user_entity_id: str, entity_id: str
    ) -> Bot:
        """
        Create bot instance from template

        Args:
            session: Database session
            template: BotTemplate instance
            user_entity_id: User's entity ID
            entity_id: Unique entity ID for the new bot

        Returns:
            Created Bot instance
        """
        try:
            new_bot = Bot(
                entity_id=entity_id,
                user_entity_id=user_entity_id,
                model=template.model,
                status="active",
                gender=template.gender,
                birthday=template.birthday,
                timezone=template.timezone,
                city_name=template.city_name,
                friend_score=template.friend_score,
                romance_score=template.romance_score,
                friend_score_cap=template.friend_score_cap,
                friend_score_floor=template.friend_score_floor,
                romance_score_cap=template.romance_score_cap,
                friend_score_pos_k=template.friend_score_pos_k,
                friend_score_neg_k=template.friend_score_neg_k,
                romance_score_k=template.romance_score_k,
                relationship_type="friend",
                relationship_level="polite",
                friend_level="polite",
                friend_buffer_status="none",
                romance_buffer_status="none",
                relationship_style=None,
                friend_config=template.friend_config,
                romance_config=template.romance_config,
                override_config=template.override_config,
                is_polite=template.is_polite,
                is_crushing=template.is_crushing,
                emotions_config=template.emotions_config,
                info=template.info,
                memory=template.memory,
            )
            session.add(new_bot)
            # Note: Don't commit here, let the calling service handle transaction

            logger.info(
                "bot_created_from_template",
                template_id=template.template_id,
                entity_id=entity_id,
                user_entity_id=user_entity_id,
            )
            return new_bot

        except Exception as e:
            logger.error(
                "create_bot_from_template_error",
                error=str(e),
                template_id=template.template_id,
                entity_id=entity_id,
                user_entity_id=user_entity_id,
            )
            raise
