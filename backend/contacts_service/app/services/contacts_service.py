"""
Contacts Service - Business logic for contact and social profile operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select
from ..database import AsyncSessionLocal
from ..models.contact import Contact
from ..models.social_profile import SocialProfile
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
            List of contact dictionaries with simplified data for frontend
            - id: contact entity_id (backend entity_id mapped to frontend id)
            - contact_type: numeric contact type (1=user, 2=bot)
            - nickname: display name
            - avatar_url: profile picture URL (prepared for future use)
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get contacts with their social profiles (no conversation mappings needed)
                result = await session.execute(
                    select(Contact, SocialProfile)
                    .join(SocialProfile, Contact.contact_entity_id == SocialProfile.entity_id)
                    .where(Contact.user_entity_id == user_entity_id)
                    .where(Contact.status == 1)  # 1=normal
                )
                contacts_with_data = result.all()

                contact_list = []
                for contact, profile in contacts_with_data:
                    contact_list.append(
                        {
                            "id": contact.contact_entity_id,  # entity_id mapped to id for frontend
                            "contact_type": contact.contact_type,  # numeric: 1=user, 2=bot
                            "nickname": profile.nickname,
                            "avatar_url": profile.avatar_url,  # prepared for future avatar support
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
            contact_entity_id: Contact's entity ID (backend entity_id)

        Returns:
            Contact dictionary with detailed profile data or None if not found
            - id: contact entity_id (backend entity_id mapped to frontend id)
            - contact_type: numeric contact type (1=user, 2=bot)
            - nickname: display name
            - bio: profile description
            - avatar_url: profile picture URL
            - location: user location
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
                    "id": contact.contact_entity_id,  # entity_id mapped to id for frontend
                    "contact_type": contact.contact_type,  # numeric: 1=user, 2=bot
                    "nickname": profile.nickname,
                    "bio": profile.bio,
                    "avatar_url": profile.avatar_url,
                    "location": profile.location,
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
            entity_id: Entity ID (backend entity_id)

        Returns:
            Social profile dictionary or None if not found
            - id: profile entity_id (backend entity_id mapped to frontend id)
            - entity_type: numeric entity type (1=user, 2=bot)
            - nickname: display name
            - avatar_url: profile picture URL
            - bio: profile description
            - birth_date: birth date
            - location: user location
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
                    "id": profile.entity_id,  # entity_id mapped to id for frontend
                    "entity_type": profile.entity_type,  # numeric: 1=user, 2=bot
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
