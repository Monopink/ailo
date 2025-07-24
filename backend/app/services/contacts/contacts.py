"""
Contacts Service - Core contact management functions
Handles contact relationships and integrates with other services
"""

import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger
from repositories.contact import ContactRepository
from repositories.bot_template import TemplateRepository
from repositories.profile import ProfileRepository
from .template import (
    search_available_templates,
    get_template_mapping,
    get_template_by_id,
    instantiate_template_to_contact,
    validate_search_timeout,
)

from .utils.contact_limits import get_user_contact_limits, check_contact_limit_reached

logger = get_logger(__name__)

# Initialize repositories
contact_repository = ContactRepository()
template_repository = TemplateRepository()
profile_repository = ProfileRepository()


async def get_user_contacts(session: AsyncSession, user_entity_id: str) -> List[Dict[str, Any]]:
    """
    Get all contacts for a user (both bot and user contacts)

    Args:
        session: Database session
        user_entity_id: User's entity ID

    Returns:
        List of contact dictionaries
    """
    try:
        # Use repository to get contacts with profiles
        contacts_data = await contact_repository.get_user_contacts_with_profiles(session, user_entity_id)

        logger.info("user_contacts_retrieved", user_entity_id=user_entity_id, count=len(contacts_data))
        return contacts_data

    except Exception as e:
        logger.error("get_user_contacts_error", error=str(e), user_entity_id=user_entity_id)
        raise


async def get_contact_by_entity_id(
    session: AsyncSession, user_entity_id: str, contact_entity_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get specific contact by entity ID

    Args:
        session: Database session
        user_entity_id: User's entity ID
        contact_entity_id: Contact's entity ID

    Returns:
        Contact dictionary or None if not found
    """
    try:
        # Get contact with profile using repository's combined method
        return await contact_repository.get_contact_with_profile(session, user_entity_id, contact_entity_id)

    except Exception as e:
        logger.error(
            "get_contact_by_entity_id_error",
            error=str(e),
            user_entity_id=user_entity_id,
            contact_entity_id=contact_entity_id,
        )
        raise


async def get_contact_chat_info(
    session: AsyncSession, user_entity_id: str, contact_entity_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get contact information for chat interface

    Args:
        session: Database session
        user_entity_id: User's entity ID
        contact_entity_id: Contact's entity ID

    Returns:
        Chat info dictionary or None if not found
    """
    try:
        # Get contact chat info using repository's combined method
        return await contact_repository.get_contact_chat_info(session, user_entity_id, contact_entity_id)

    except Exception as e:
        logger.error(
            "get_contact_chat_info_error",
            error=str(e),
            user_entity_id=user_entity_id,
            contact_entity_id=contact_entity_id,
        )
        raise


async def search_contacts(session: AsyncSession, user_entity_id: str, query: str) -> List[Dict[str, Any]]:
    """
    Search available contacts from templates

    Args:
        session: Database session
        user_entity_id: User's entity ID
        query: Search query

    Returns:
        List of available contact dictionaries
    """
    try:
        return await search_available_templates(session, user_entity_id, query)

    except Exception as e:
        logger.error("search_contacts_error", error=str(e), user_entity_id=user_entity_id, query=query)
        raise


async def add_contact(session: AsyncSession, user_entity_id: str, contact_entity_id: str) -> Dict[str, Any]:
    """
    Add a new contact from template mapping

    Args:
        session: Database session
        user_entity_id: User's entity ID
        contact_entity_id: Contact entity ID (from template_mappings.entity_id)

    Returns:
        Result dictionary with status and message
    """
    start_time = time.time()
    try:
        # Start explicit transaction for rollback capability
        async with session.begin():
            # Check user's contact limits first
            limits_info = await get_user_contact_limits(session, user_entity_id)
            if check_contact_limit_reached(limits_info):
                logger.warning(
                    "add_contact_limit_reached",
                    user_entity_id=user_entity_id,
                    current_count=limits_info["current_count"],
                    contact_limit=limits_info["contact_limit"],
                    reason="Contact limit reached",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Get template mapping
            mapping = await get_template_mapping(session, user_entity_id, contact_entity_id)
            if not mapping:
                logger.warning(
                    "add_contact_invalid_mapping",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    reason="Template mapping not found or inactive",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Check search timeout
            if not validate_search_timeout(mapping):
                logger.warning(
                    "add_contact_search_timeout",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    reason="Search timeout exceeded or no search record",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Check if contact already exists using repository
            existing_contact = await contact_repository.get_contact_by_entities(
                session, user_entity_id, contact_entity_id
            )

            if existing_contact:
                logger.warning(
                    "add_contact_already_exists",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    reason="Contact already added",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Get template data
            template = await get_template_by_id(session, mapping.template_id)
            if not template:
                logger.warning(
                    "add_contact_template_not_found",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    template_id=mapping.template_id,
                    reason="Template data not found",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Check template availability
            if template.template_status != "active":
                logger.warning(
                    "add_contact_template_disabled",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    template_id=template.template_id,
                    template_status=template.template_status,
                    reason="Template is disabled",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            if template.remaining_uses is not None and template.remaining_uses == 0:
                logger.warning(
                    "add_contact_template_exhausted",
                    user_entity_id=user_entity_id,
                    contact_entity_id=contact_entity_id,
                    template_id=template.template_id,
                    remaining_uses=template.remaining_uses,
                    reason="Template usage exhausted",
                )
                return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}

            # Generate unique entity_id for this user's bot instance
            from utils.id_generator import generate_unique_entity_id

            unique_entity_id = await generate_unique_entity_id(session)

            # Instantiate template to create bot and profile
            await instantiate_template_to_contact(session, template, user_entity_id, unique_entity_id)

            # Create contact record using repository
            await contact_repository.create_contact_relationship(
                session, user_entity_id, unique_entity_id, contact_type=2
            )

            # Decrease template remaining uses
            await template_repository.decrease_template_usage(session, template)

            # Update template mapping status to inactive to prevent re-selection
            mapping.status = "inactive"

        # Transaction will auto-commit here if no exceptions

        execution_time = time.time() - start_time
        logger.info(
            "contact_added_successfully",
            user_entity_id=user_entity_id,
            contact_entity_id=unique_entity_id,
            template_id=template.template_id,
            nickname=template.nickname,
            remaining_uses=template.remaining_uses,
            execution_time_ms=round(execution_time * 1000, 2),
        )

        # Send system message notification
        await _send_new_contact_system_message(
            contact_entity_id=unique_entity_id,
            user_entity_id=user_entity_id,
            contact_name=template.nickname,
        )

        return {
            "status": "success",
            "message": "申请已发送",
            "contact": {"id": unique_entity_id, "nickname": template.nickname},
        }

    except Exception as e:
        logger.error(
            "add_contact_unexpected_error",
            error=str(e),
            user_entity_id=user_entity_id,
            contact_entity_id=contact_entity_id,
            reason="Unexpected error during contact addition",
        )
        return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}


async def _send_new_contact_system_message(
    contact_entity_id: str, user_entity_id: str, contact_name: str
) -> None:
    """
    Send system message notification for new contact

    Args:
        contact_entity_id: Contact's entity ID
        user_entity_id: User's entity ID
        contact_name: Contact's name
    """
    try:
        # Import the unified message module
        from ..message.message import send_system_message
        from enums import SystemMessageAction

        logger.info(
            "sending_new_contact_system_message",
            contact_entity_id=contact_entity_id,
            user_entity_id=user_entity_id,
            contact_name=contact_name,
        )

        # Send NEW_CONTACT system message using unified function
        await send_system_message(
            from_entity=str(contact_entity_id),  # Bot entity_id as string, no prefix
            to_entity=str(user_entity_id),
            action=SystemMessageAction.NEW_CONTACT,
            contact_id=contact_entity_id,
        )

        logger.info(
            "new_contact_system_message_sent",
            contact_entity_id=contact_entity_id,
            user_entity_id=user_entity_id,
            contact_name=contact_name,
        )
    except Exception as e:
        logger.error(
            "new_contact_system_message_error",
            error=str(e),
            contact_entity_id=contact_entity_id,
            user_entity_id=user_entity_id,
        )
        # Don't re-raise to avoid blocking contact addition
