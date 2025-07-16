"""
Contacts Service - Core contact management functions
Handles contact relationships and integrates with other services
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_
from ..database import AsyncSessionLocal
from ..models.contact import Contact
from .template_service import (
    search_available_templates,
    get_template_mapping,
    get_template_by_id,
    instantiate_template_to_contact,
    decrease_template_usage,
    validate_search_timeout,
)
from .profile_service import get_social_profile
from .utils.user_limits import get_user_contact_limits, check_contact_limit_reached
import requests
import time
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ContactsService:
    """Contact management service with integrated template and profile services"""

    async def get_user_contacts(self, user_entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all contacts for a user (both bot and user contacts)

        Args:
            user_entity_id: User's entity ID

        Returns:
            List of contact dictionaries
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get all contacts (both bot and user contacts)
                contacts_result = await session.execute(
                    select(Contact).where(
                        and_(
                            Contact.user_entity_id == user_entity_id,
                            Contact.status == 1,  # normal status
                        )
                    )
                )

                contacts_data = []
                for contact in contacts_result.scalars().all():
                    # Get social profile for display info
                    profile = await get_social_profile(session, contact.contact_entity_id)

                    contact_info = {
                        "id": contact.contact_entity_id,  # Use entity_id as id for frontend
                        "contact_type": contact.contact_type,  # Add contact_type field
                        "nickname": profile.get("nickname") if profile else None,
                        "avatar_url": profile.get("avatar_url") if profile else None,
                        "gender": profile.get("gender") if profile else None,
                        "location": profile.get("location") if profile else None,
                        "created_at": contact.created_at.isoformat() if contact.created_at else None,
                    }
                    contacts_data.append(contact_info)

                logger.info(
                    "user_contacts_retrieved", user_entity_id=user_entity_id, count=len(contacts_data)
                )
                return contacts_data

        except Exception as e:
            logger.error("get_user_contacts_error", error=str(e), user_entity_id=user_entity_id)
            raise

    async def get_contact_by_entity_id(
        self, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific contact by entity ID

        Args:
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Contact dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                # Check if contact exists for this user (support both user and bot contacts)
                contact_result = await session.execute(
                    select(Contact).where(
                        and_(
                            Contact.user_entity_id == user_entity_id,
                            Contact.contact_entity_id == contact_entity_id,
                            Contact.status == 1,  # normal status
                        )
                    )
                )
                contact = contact_result.scalar_one_or_none()

                if not contact:
                    return None

                # Get social profile
                profile = await get_social_profile(session, contact_entity_id)

                return {
                    "contact_id": contact.id,
                    "entity_id": contact_entity_id,
                    "nickname": profile.get("nickname") if profile else None,
                    "avatar_url": profile.get("avatar_url") if profile else None,
                    "gender": profile.get("gender") if profile else None,
                    "bio": profile.get("bio") if profile else None,
                    "location": profile.get("location") if profile else None,
                    "created_at": contact.created_at.isoformat() if contact.created_at else None,
                }

        except Exception as e:
            logger.error(
                "get_contact_by_entity_id_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def get_contact_chat_info(
        self, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get contact information for chat interface

        Args:
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Chat info dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                # Verify contact relationship exists (support both user and bot contacts)
                contact_result = await session.execute(
                    select(Contact).where(
                        and_(
                            Contact.user_entity_id == user_entity_id,
                            Contact.contact_entity_id == contact_entity_id,
                            Contact.status == 1,  # normal status
                        )
                    )
                )
                contact = contact_result.scalar_one_or_none()

                if not contact:
                    return None

                # Get social profile for chat display
                profile = await get_social_profile(session, contact_entity_id)

                return {
                    "id": contact_entity_id,  # Use entity_id as id for frontend
                    "nickname": profile.get("nickname") if profile else None,
                    "avatar_url": profile.get("avatar_url") if profile else None,
                    "contact_type": contact.contact_type,  # Use actual contact type
                }

        except Exception as e:
            logger.error(
                "get_contact_chat_info_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def search_contacts(self, user_entity_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Search available contacts from templates

        Args:
            user_entity_id: User's entity ID
            query: Search query

        Returns:
            List of available contact dictionaries
        """
        try:
            async with AsyncSessionLocal() as session:
                return await search_available_templates(session, user_entity_id, query)

        except Exception as e:
            logger.error("search_contacts_error", error=str(e), user_entity_id=user_entity_id, query=query)
            raise

    async def add_contact(self, user_entity_id: str, contact_entity_id: str) -> Dict[str, Any]:
        """
        Add a new contact from template mapping

        Args:
            user_entity_id: User's entity ID
            contact_entity_id: Contact entity ID (from template_mappings.entity_id)

        Returns:
            Result dictionary with status and message
        """
        start_time = time.time()
        try:
            async with AsyncSessionLocal() as session:
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

                    # Check if contact already exists
                    existing_contact = await session.execute(
                        select(Contact).where(
                            and_(
                                Contact.user_entity_id == user_entity_id,
                                Contact.contact_entity_id == contact_entity_id,
                                Contact.contact_type == 2,  # bot contact
                                Contact.status == 1,  # normal status
                            )
                        )
                    )

                    if existing_contact.scalar_one_or_none():
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
                    from ..utils.id_generator import generate_unique_entity_id

                    unique_entity_id = await generate_unique_entity_id(session)

                    # Instantiate template to create bot and profile
                    await instantiate_template_to_contact(
                        session, template, user_entity_id, unique_entity_id
                    )

                    # Create contact record
                    new_contact = Contact(
                        user_entity_id=user_entity_id,
                        contact_entity_id=unique_entity_id,
                        contact_type=2,  # bot contact
                        status=1,  # normal
                    )
                    session.add(new_contact)

                    # Decrease template remaining uses
                    decrease_template_usage(template)

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
                await self._send_new_contact_system_message(
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
        self, contact_entity_id: str, user_entity_id: str, contact_name: str
    ) -> None:
        """
        Send system message notification for new contact

        Args:
            contact_entity_id: Contact's entity ID
            user_entity_id: User's entity ID
            contact_name: Contact's name
        """
        try:
            # System message payload according to message-formats.md
            # This is a NEW_CONTACT system message (action: 2)
            # No message field - frontend will use default message
            # No contact_name field - not needed by frontend
            system_message_data = {
                "from_entity": str(contact_entity_id),  # Bot entity_id as string, no prefix
                "to_user": str(user_entity_id),
                "content": {
                    "action": 2,  # NEW_CONTACT action
                    "contact_id": contact_entity_id,
                },
            }

            logger.info(
                "sending_new_contact_system_message",
                contact_entity_id=contact_entity_id,
                user_entity_id=user_entity_id,
                contact_name=contact_name,
                system_message_data=system_message_data,
            )

            # Send to bot message service with correct URL and authentication
            bot_message_service_url = "http://bot_message_service_container:8000/api/v1/system/send-message"

            # Get internal service key from settings
            from ..core.config import settings

            headers = {"Content-Type": "application/json", "X-Internal-Key": settings.INTERNAL_SERVICE_KEY}

            response = requests.post(
                bot_message_service_url,
                json=system_message_data,
                timeout=5,
                headers=headers,
            )

            logger.info(
                "system_message_response_received",
                status_code=response.status_code,
                response_text=response.text[:200] if response.text else None,  # Limit log size
                url=bot_message_service_url,
            )

            if response.status_code == 200:
                logger.info(
                    "new_contact_system_message_sent",
                    contact_entity_id=contact_entity_id,
                    user_entity_id=user_entity_id,
                    contact_name=contact_name,
                )
            else:
                logger.warning(
                    "new_contact_system_message_failed",
                    contact_entity_id=contact_entity_id,
                    user_entity_id=user_entity_id,
                    status_code=response.status_code,
                    response_text=response.text,
                )

        except requests.exceptions.RequestException as e:
            logger.warning(
                "new_contact_system_message_request_error",
                error=str(e),
                contact_entity_id=contact_entity_id,
                user_entity_id=user_entity_id,
            )
        except Exception as e:
            logger.error(
                "new_contact_system_message_error",
                error=str(e),
                contact_entity_id=contact_entity_id,
                user_entity_id=user_entity_id,
            )
            # Don't re-raise to avoid blocking contact addition

    async def get_user_contact_limits(self, user_entity_id: str) -> Dict[str, Any]:
        """
        Get user's contact limits and current count (wrapper for compatibility)

        Args:
            user_entity_id: User's entity ID

        Returns:
            Dictionary with contact limits and current count
        """
        try:
            async with AsyncSessionLocal() as session:
                return await get_user_contact_limits(session, user_entity_id)
        except Exception as e:
            logger.error("get_user_contact_limits_error", error=str(e), user_entity_id=user_entity_id)
            raise

    async def get_social_profile_by_entity_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get social profile by entity ID (wrapper for compatibility)

        Args:
            entity_id: Entity ID

        Returns:
            Social profile dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                return await get_social_profile(session, entity_id)
        except Exception as e:
            logger.error("get_social_profile_by_entity_id_error", error=str(e), entity_id=entity_id)
            raise

    async def create_or_update_social_profile(
        self, entity_id: str, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update social profile (wrapper for compatibility)

        Args:
            entity_id: Entity ID
            profile_data: Profile data dictionary

        Returns:
            Profile dictionary
        """
        try:
            from .profile_service import create_or_update_social_profile

            async with AsyncSessionLocal() as session:
                return await create_or_update_social_profile(session, entity_id, profile_data)
        except Exception as e:
            logger.error("create_or_update_social_profile_error", error=str(e), entity_id=entity_id)
            raise


# Create global instance
contacts_service = ContactsService()
