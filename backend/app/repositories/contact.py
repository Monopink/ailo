from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from models.contact import Contact
from models.user import User
from utils.logging import get_logger
from .base import BaseRepository

logger = get_logger(__name__)


class ContactRepository:
    """Repository for contact relationship data operations"""

    def __init__(self, profile_repo=None):
        # Initialize base repository for Contact model
        self.contact_repo = BaseRepository(Contact)
        self.user_repo = BaseRepository(User)

        # Dependency injection for ProfileRepository
        if profile_repo is None:
            from .profile import ProfileRepository

            self.profile_repo = ProfileRepository()
        else:
            self.profile_repo = profile_repo

    # Contact relationship operations
    async def get_user_contacts_with_profiles(
        self, session: AsyncSession, user_entity_id: str, status: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get user contacts with their social profiles

        Args:
            session: Database session
            user_entity_id: User's entity ID
            status: Contact status (1=normal, 2=blocked, etc.)

        Returns:
            List of contact dictionaries with profile information
        """
        try:
            # Get all contacts for the user
            contacts_result = await session.execute(
                select(Contact)
                .where(
                    and_(
                        Contact.user_entity_id == user_entity_id,
                        Contact.status == status,
                    )
                )
                .order_by(desc(Contact.created_at))
            )
            contacts = contacts_result.scalars().all()

            # Build contact list with profile information
            contacts_data = []
            for contact in contacts:
                # Get social profile for display info using injected ProfileRepository
                profile = await self.profile_repo.get_social_profile_by_entity_id(
                    session, contact.contact_entity_id
                )

                contact_info = {
                    "id": contact.contact_entity_id,  # Use entity_id as id for frontend
                    "contact_type": contact.contact_type,
                    "nickname": profile.get("nickname") if profile else None,
                    "avatar_url": profile.get("avatar_url") if profile else None,
                    "gender": profile.get("gender") if profile else None,
                    "location": profile.get("location") if profile else None,
                    "created_at": contact.created_at.isoformat() if contact.created_at else None,
                }
                contacts_data.append(contact_info)

            logger.info("user_contacts_retrieved", user_entity_id=user_entity_id, count=len(contacts_data))
            return contacts_data

        except Exception as e:
            logger.error(
                "get_user_contacts_with_profiles_error", error=str(e), user_entity_id=user_entity_id
            )
            raise

    async def get_contact_by_entities(
        self, session: AsyncSession, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Contact]:
        """
        Get contact relationship by user and contact entity IDs

        Args:
            session: Database session
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Contact instance or None if not found
        """
        try:
            result = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.user_entity_id == user_entity_id,
                        Contact.contact_entity_id == contact_entity_id,
                        Contact.status == 1,  # normal status
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                "get_contact_by_entities_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def create_contact_relationship(
        self, session: AsyncSession, user_entity_id: str, contact_entity_id: str, contact_type: int = 2
    ) -> Contact:
        """
        Create a new contact relationship

        Args:
            session: Database session
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID
            contact_type: Contact type (1=user, 2=bot)

        Returns:
            Created Contact instance
        """
        try:
            new_contact = Contact(
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
                contact_type=contact_type,
                status=1,  # normal
            )
            session.add(new_contact)
            # Note: Don't commit here, let the calling service handle transaction

            logger.info(
                "contact_relationship_created",
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
                contact_type=contact_type,
            )
            return new_contact

        except Exception as e:
            logger.error(
                "create_contact_relationship_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def get_contact_with_profile(
        self, session: AsyncSession, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get contact relationship with social profile data

        Args:
            session: Database session
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Combined contact and profile dictionary or None if not found
        """
        try:
            # Get contact relationship
            contact = await self.get_contact_by_entities(session, user_entity_id, contact_entity_id)
            if not contact:
                return None

            # Get social profile using injected ProfileRepository
            profile = await self.profile_repo.get_social_profile_by_entity_id(session, contact_entity_id)

            # Combine contact and profile data
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
                "get_contact_with_profile_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    async def get_contact_chat_info(
        self, session: AsyncSession, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get contact information for chat display

        Args:
            session: Database session
            user_entity_id: User's entity ID
            contact_entity_id: Contact's entity ID

        Returns:
            Contact chat info dictionary or None if not found
        """
        try:
            # Get contact relationship
            contact = await self.get_contact_by_entities(session, user_entity_id, contact_entity_id)
            if not contact:
                return None

            # Get social profile using injected ProfileRepository
            profile = await self.profile_repo.get_social_profile_by_entity_id(session, contact_entity_id)

            # Return chat-specific info
            return {
                "id": contact_entity_id,
                "nickname": profile.get("nickname") if profile else "Unknown",
                "avatar_url": profile.get("avatar_url") if profile else None,
                "contact_type": contact.contact_type,
            }

        except Exception as e:
            logger.error(
                "get_contact_chat_info_error",
                error=str(e),
                user_entity_id=user_entity_id,
                contact_entity_id=contact_entity_id,
            )
            raise

    # User operations
    async def get_user_contact_limits(self, session: AsyncSession, user_entity_id: str) -> Dict[str, Any]:
        """
        Get user's contact limits and current count

        Args:
            session: Database session
            user_entity_id: User's entity ID

        Returns:
            Dictionary with contact limits and current count
        """
        try:
            # Get user settings
            user_result = await session.execute(select(User).where(User.entity_id == user_entity_id))
            user = user_result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User not found: {user_entity_id}")

            # Count current bot contacts
            contact_count_result = await session.execute(
                select(func.count(Contact.id)).where(
                    Contact.user_entity_id == user_entity_id,
                    Contact.contact_type == 2,  # bot contacts only
                    Contact.status == 1,  # normal status only
                )
            )
            current_count = contact_count_result.scalar() or 0

            return {
                "current_count": current_count,
                "contact_limit": user.contact_limit,
                "search_display_limit": user.search_display_limit,
                "can_add_more": current_count < user.contact_limit,
            }

        except Exception as e:
            logger.error("get_user_contact_limits_error", error=str(e), user_entity_id=user_entity_id)
            raise
