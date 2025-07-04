"""
Contacts Service - Business logic for contact and social profile operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select
from ..database import AsyncSessionLocal
from ..models.contact import Contact
from ..models.social_profile import SocialProfile
from ..models.conversation_mapping import ConversationMapping
import structlog

logger = structlog.get_logger(__name__)


class ContactsService:
    """Service class for contact and social profile operations"""

    async def get_user_contacts(self, user_entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all contacts for a specific user with their social profiles

        Args:
            user_entity_id: User's entity ID

        Returns:
            List of contact dictionaries with social profile data
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get contacts with their social profiles and conversation mappings
                result = await session.execute(
                    select(Contact, SocialProfile, ConversationMapping)
                    .join(SocialProfile, Contact.contact_entity_id == SocialProfile.entity_id)
                    .outerjoin(
                        ConversationMapping,
                        (ConversationMapping.contact_entity_id == Contact.contact_entity_id)
                        & (ConversationMapping.im_service_type == "leancloud"),  # Use string value
                    )
                    .where(Contact.user_entity_id == user_entity_id)
                    .where(Contact.status == 1)  # 1=normal
                )
                contacts_with_data = result.all()

                contact_list = []
                for contact, profile, mapping in contacts_with_data:
                    # Debug logging
                    logger.info(
                        "processing_contact",
                        entity_id=contact.contact_entity_id,
                        mapping_exists=mapping is not None,
                        conversation_id=mapping.conversation_id if mapping else None,
                    )

                    contact_list.append(
                        {
                            "id": contact.id,
                            "entity_id": contact.contact_entity_id,
                            "contact_type": contact.contact_type,
                            "nickname": profile.nickname,
                            "bio": profile.bio,
                            "avatar_url": profile.avatar_url,
                            "location": profile.location,
                            "last_message_time": contact.last_message_time,
                            "unread_count": contact.unread_count,
                            "is_pinned": contact.is_pinned,
                            "remark": contact.remark,
                            "status": contact.status,
                            "leancloud_conversation_id": mapping.conversation_id if mapping else None,
                            "debug_mapping_exists": mapping is not None,
                        }
                    )

                logger.info(
                    "user_contacts_retrieved", user_entity_id=user_entity_id, count=len(contact_list)
                )
                return contact_list

        except Exception as e:
            logger.error("get_user_contacts_error", error=str(e), user_entity_id=user_entity_id)
            raise

    async def get_contact_by_entity_id(
        self, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific contact by entity ID with social profile

        Args:
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Contact dictionary with social profile or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Contact, SocialProfile)
                    .join(SocialProfile, Contact.contact_entity_id == SocialProfile.entity_id)
                    .where(Contact.user_entity_id == user_entity_id)
                    .where(Contact.contact_entity_id == contact_entity_id)
                )
                contact_with_profile = result.first()

                if not contact_with_profile:
                    return None

                contact, profile = contact_with_profile
                return {
                    "id": contact.id,
                    "entity_id": contact.contact_entity_id,
                    "contact_type": contact.contact_type,
                    "nickname": profile.nickname,
                    "bio": profile.bio,
                    "avatar_url": profile.avatar_url,
                    "location": profile.location,
                    "last_message_time": contact.last_message_time,
                    "unread_count": contact.unread_count,
                    "is_pinned": contact.is_pinned,
                    "remark": contact.remark,
                    "status": contact.status,
                }

        except Exception as e:
            logger.error(
                "get_contact_by_entity_id_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def get_social_profile_by_entity_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get social profile by entity ID

        Args:
            entity_id: Entity ID

        Returns:
            Social profile dictionary or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SocialProfile).where(SocialProfile.entity_id == entity_id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    return None

                return {
                    "entity_id": profile.entity_id,
                    "entity_type": profile.entity_type,
                    "nickname": profile.nickname,
                    "avatar_url": profile.avatar_url,
                    "bio": profile.bio,
                    "birth_date": profile.birth_date,
                    "location": profile.location,
                }

        except Exception as e:
            logger.error("get_social_profile_by_entity_id_error", error=str(e), entity_id=entity_id)
            raise


# Create global instance
contacts_service = ContactsService()
