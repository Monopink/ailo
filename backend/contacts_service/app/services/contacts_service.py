"""
Contacts Service - Business logic for contact and social profile operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
            - gender: gender (male/female/other)
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
                    "gender": profile.gender,
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
            - nickname: display name
            - gender: gender (male/female/other)
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
                    "nickname": profile.nickname,
                    "gender": profile.gender,
                    "avatar_url": profile.avatar_url,
                    "bio": profile.bio,
                    "birth_date": profile.birth_date,
                    "location": profile.location,
                }

        except Exception as e:
            logger.error("get_social_profile_by_entity_id_error", error=str(e), entity_id=entity_id)
            raise

    async def create_or_update_social_profile(
        self, entity_id: str, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update social profile for a user

        Args:
            entity_id: User's entity ID
            profile_data: Profile data to create/update

        Returns:
            Updated social profile dictionary
        """
        try:
            async with AsyncSessionLocal() as session:
                # Check if profile exists
                result = await session.execute(
                    select(SocialProfile).where(SocialProfile.entity_id == entity_id)
                )
                existing_profile = result.scalar_one_or_none()

                if existing_profile:
                    # Update existing profile
                    for key, value in profile_data.items():
                        if hasattr(existing_profile, key) and value is not None:
                            setattr(existing_profile, key, value)

                    await session.commit()
                    await session.refresh(existing_profile)
                    profile = existing_profile
                else:
                    # Create new profile
                    profile = SocialProfile(entity_id=entity_id, **profile_data)
                    session.add(profile)
                    await session.commit()
                    await session.refresh(profile)

                logger.info(
                    "social_profile_created_or_updated",
                    entity_id=entity_id,
                    action="updated" if existing_profile else "created",
                )

                return {
                    "id": profile.entity_id,
                    "nickname": profile.nickname,
                    "gender": profile.gender,
                    "avatar_url": profile.avatar_url,
                    "bio": profile.bio,
                    "birth_date": profile.birth_date,
                    "location": profile.location,
                }

        except IntegrityError as e:
            logger.error(
                "create_or_update_social_profile_integrity_error", error=str(e), entity_id=entity_id
            )
            raise
        except Exception as e:
            logger.error("create_or_update_social_profile_error", error=str(e), entity_id=entity_id)
            raise

    async def get_contact_chat_info(
        self, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific contact's chat display information

        Args:
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Contact chat info dictionary or None if not found
            - id: contact entity_id (backend entity_id mapped to frontend id)
            - nickname: display name
            - avatar_url: profile picture URL (prepared for future use)
            - last_updated: profile last update time
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Contact, SocialProfile)
                    .join(SocialProfile, Contact.contact_entity_id == SocialProfile.entity_id)
                    .where(Contact.user_entity_id == user_entity_id)
                    .where(Contact.contact_entity_id == contact_entity_id)
                    .where(Contact.status == 1)  # 1=normal
                )
                contact_with_profile = result.first()

                if not contact_with_profile:
                    return None

                contact, profile = contact_with_profile
                return {
                    "id": contact.contact_entity_id,  # entity_id mapped to id for frontend
                    "nickname": profile.nickname,
                    "avatar_url": profile.avatar_url,
                    "last_updated": profile.updated_at.isoformat() if profile.updated_at else None,
                }

        except Exception as e:
            logger.error(
                "get_contact_chat_info_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise


# Create global instance
contacts_service = ContactsService()
