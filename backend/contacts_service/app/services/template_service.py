"""
Template Service - Template search, mapping, and instantiation functions
Handles bot template related operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from ..models.bot_template import BotTemplate
from ..models.template_mapping import TemplateMapping
from ..models.contact import Contact
from ..models.bot import Bot
from ..models.social_profile import SocialProfile
from ..utils.id_generator import generate_unique_entity_id
from .utils.weight_selection import weighted_random_selection
from .utils.user_limits import (
    get_user_contact_limits,
    check_contact_limit_reached,
    get_search_display_limit,
)
from ..core.config import settings
from ..utils.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


async def search_available_templates(
    session: AsyncSession, user_entity_id: str, query: str
) -> List[Dict[str, Any]]:
    """
    Search available templates for user

    Args:
        session: Database session
        user_entity_id: User's entity ID
        query: Search query

    Returns:
        List of available template dictionaries
    """
    try:
        # Get user's contact limits
        limits_info = await get_user_contact_limits(session, user_entity_id)

        # Check if user can add more contacts
        if check_contact_limit_reached(limits_info):
            logger.info(
                "search_templates_limit_reached",
                user_entity_id=user_entity_id,
                current_count=limits_info["current_count"],
                contact_limit=limits_info["contact_limit"],
            )
            return []

        # Get search display limit
        search_limit = get_search_display_limit(limits_info)

        # Get available bot templates
        available_templates = await session.execute(
            select(BotTemplate).where(
                and_(
                    BotTemplate.template_status == "active",
                    func.coalesce(BotTemplate.remaining_uses, -1)
                    != 0,  # Not exhausted (0 means exhausted, -1 means unlimited)
                )
            )
        )
        templates = available_templates.scalars().all()

        if not templates:
            logger.info("search_templates_no_templates", user_entity_id=user_entity_id)
            return []

        # Filter out templates that user has already added as contacts
        existing_contacts = await session.execute(
            select(Contact.contact_entity_id).where(
                and_(
                    Contact.user_entity_id == user_entity_id,
                    Contact.contact_type == 2,  # bot contact
                    Contact.status == 1,  # normal status
                )
            )
        )
        existing_contact_ids = {row[0] for row in existing_contacts.fetchall()}

        # Get existing template mappings for this user (all statuses)
        existing_mappings = await session.execute(
            select(TemplateMapping).where(TemplateMapping.user_entity_id == user_entity_id)
        )
        mappings_dict = {mapping.template_id: mapping for mapping in existing_mappings.scalars().all()}

        # Filter templates and prepare for selection
        available_for_selection = []
        for template in templates:
            # Skip if user already has this template as a contact
            if template.template_id in mappings_dict:
                mapping = mappings_dict[template.template_id]
                if mapping.entity_id in existing_contact_ids:
                    continue
                # Skip if mapping exists but is inactive (already added before)
                if mapping.status == "inactive":
                    continue

            available_for_selection.append(template)

        if not available_for_selection:
            logger.info("search_templates_all_added", user_entity_id=user_entity_id)
            return []

        # Weighted random selection
        selected_templates = weighted_random_selection(available_for_selection, search_limit)

        # Process selected templates and create/update mappings
        result_templates = []
        for template in selected_templates:
            # Get or create template mapping
            if template.template_id in mappings_dict:
                mapping = mappings_dict[template.template_id]
                # Update last search time and reactivate if inactive
                mapping.last_search_time = datetime.now()
                if mapping.status == "inactive":
                    mapping.status = "active"
            else:
                # Create new mapping
                unique_entity_id = await generate_unique_entity_id(session)

                mapping = TemplateMapping(
                    entity_id=unique_entity_id,
                    user_entity_id=user_entity_id,
                    template_id=template.template_id,
                    last_search_time=datetime.now(),
                    status="active",
                )
                session.add(mapping)

            # Prepare result data (without bio field)
            template_data = {
                "id": mapping.entity_id,  # Use mapping entity_id as frontend id
                "nickname": template.nickname,
                "avatar_url": template.avatar_url,
                "gender": template.gender,
                "location": template.location,
            }
            result_templates.append(template_data)

        # Commit mapping changes
        await session.commit()

        logger.info(
            "search_templates_completed",
            user_entity_id=user_entity_id,
            query=query,
            total_available=len(available_for_selection),
            returned_count=len(result_templates),
            search_limit=search_limit,
        )

        return result_templates

    except Exception as e:
        logger.error("search_templates_error", error=str(e), user_entity_id=user_entity_id, query=query)
        raise


def validate_search_timeout(mapping: TemplateMapping) -> bool:
    """
    Validate if search timeout has not exceeded

    Args:
        mapping: Template mapping to check

    Returns:
        True if within timeout, False if exceeded
    """
    if not mapping.last_search_time:
        return False

    time_diff = (datetime.now() - mapping.last_search_time).total_seconds()
    return time_diff <= settings.ADD_CONTACT_TIMEOUT


async def get_template_mapping(
    session: AsyncSession, user_entity_id: str, entity_id: str
) -> Optional[TemplateMapping]:
    """
    Get template mapping by user and entity ID

    Args:
        session: Database session
        user_entity_id: User's entity ID
        entity_id: Template mapping entity ID

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
            "get_template_mapping_error", error=str(e), user_entity_id=user_entity_id, entity_id=entity_id
        )
        raise


async def get_template_by_id(session: AsyncSession, template_id: str) -> Optional[BotTemplate]:
    """
    Get bot template by template ID

    Args:
        session: Database session
        template_id: Template ID

    Returns:
        BotTemplate instance or None
    """
    try:
        result = await session.execute(select(BotTemplate).where(BotTemplate.template_id == template_id))
        return result.scalar_one_or_none()

    except Exception as e:
        logger.error("get_template_by_id_error", error=str(e), template_id=template_id)
        raise


async def instantiate_template_to_contact(
    session: AsyncSession, template: BotTemplate, user_entity_id: str, entity_id: str
) -> Dict[str, Any]:
    """
    Instantiate template to create bot and social profile

    Args:
        session: Database session
        template: BotTemplate instance
        user_entity_id: User's entity ID
        entity_id: Unique entity ID for the new contact

    Returns:
        Result dictionary
    """
    try:
        # Create bot record from template data
        new_bot = Bot(
            entity_id=entity_id,
            user_entity_id=user_entity_id,
            model=template.model,
            status="active",  # Set as active for new bot
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
            relationship_type="friend",  # Default relationship type
            relationship_level="polite",  # Default relationship level
            friend_level="polite",  # Default friend level
            friend_buffer_status="none",  # Default buffer status
            romance_buffer_status="none",  # Default buffer status
            relationship_style=None,  # Will be set based on relationship level
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

        # Create social profile record from template data
        new_profile = SocialProfile(
            entity_id=entity_id,
            nickname=template.nickname,
            gender=template.gender,
            bio=template.bio,
            avatar_url=template.avatar_url,
            birth_date=template.birth_date,  # Use birth_date field for social profile
            location=template.location,
        )
        session.add(new_profile)

        logger.info(
            "template_instantiated",
            template_id=template.template_id,
            entity_id=entity_id,
            user_entity_id=user_entity_id,
            nickname=template.nickname,
        )

        return {"bot": new_bot, "profile": new_profile}

    except Exception as e:
        logger.error(
            "template_instantiation_error",
            error=str(e),
            template_id=template.template_id,
            entity_id=entity_id,
            user_entity_id=user_entity_id,
        )
        raise


def decrease_template_usage(template: BotTemplate) -> None:
    """
    Decrease template remaining uses

    Args:
        template: BotTemplate instance to update
    """
    try:
        # Decrease template remaining uses if not unlimited
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
