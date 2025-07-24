"""
Template Service - Template search, mapping, and instantiation functions
Handles bot template related operations
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from models.template_mapping import TemplateMapping
from models.bot_template import BotTemplate
from utils.id_generator import generate_unique_entity_id
from utils.logging import get_logger
from repositories.contact import ContactRepository
from repositories.bot_template import TemplateRepository
from repositories.profile import ProfileRepository
from .utils.weight_selection import weighted_random_selection
from .utils.contact_limits import (
    check_contact_limit_reached,
    get_search_display_limit,
)

logger = get_logger(__name__)

# Initialize repositories
contact_repository = ContactRepository()
template_repository = TemplateRepository()
profile_repository = ProfileRepository()


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
        # Get user's contact limits using repository
        limits_info = await contact_repository.get_user_contact_limits(session, user_entity_id)

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

        # Get available bot templates using repository
        templates = await template_repository.get_available_templates(session)

        if not templates:
            logger.info("search_templates_no_templates", user_entity_id=user_entity_id)
            return []

        # Get user's existing contacts to filter out already added templates
        user_contacts = await contact_repository.get_user_contacts_with_profiles(session, user_entity_id)
        existing_contact_ids = {contact["id"] for contact in user_contacts}

        # Get template IDs from available templates
        template_ids = [template.template_id for template in templates]

        # Get existing template mappings for this user
        mappings_dict = await template_repository.get_template_mappings_by_user(
            session, user_entity_id, template_ids
        )

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
                # Update last search time and reactivate if inactive using repository
                await template_repository.update_template_mapping_search_time(session, mapping)
            else:
                # Create new mapping using repository
                unique_entity_id = await generate_unique_entity_id(session)

                mapping = await template_repository.create_template_mapping(
                    session, unique_entity_id, user_entity_id, template.template_id
                )

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
        return await template_repository.get_template_mapping_by_entity_id(
            session, user_entity_id, entity_id
        )

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
        return await template_repository.get_template_by_id(session, template_id)

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
        # Create bot record from template using repository
        new_bot = await template_repository.create_bot_from_template(
            session, template, user_entity_id, entity_id
        )

        # Create social profile record from template using repository
        profile_data = {
            "nickname": template.nickname,
            "gender": template.gender,
            "bio": template.bio,
            "avatar_url": template.avatar_url,
            "birth_date": template.birth_date,
            "location": template.location,
        }
        new_profile = await profile_repository.create_social_profile(session, entity_id, profile_data)

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
