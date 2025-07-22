from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.exc import IntegrityError
from models.contact import Contact
from models.social_profile import SocialProfile
from models.user import User
from schemas.contact import ContactCreate, ContactUpdate
from utils.logging import get_logger

logger = get_logger(__name__)


class ContactCRUD:
    """CRUD operations for contact management"""

    async def get_contact_by_id(self, db: AsyncSession, contact_id: int) -> Optional[Contact]:
        """Get contact by ID"""
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        return result.scalar_one_or_none()

    async def get_contact_by_entities(
        self, db: AsyncSession, user_entity_id: str, contact_entity_id: str
    ) -> Optional[Contact]:
        """Get contact relationship by user and contact entity IDs"""
        result = await db.execute(
            select(Contact).where(
                and_(
                    Contact.user_entity_id == user_entity_id, Contact.contact_entity_id == contact_entity_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_contacts(
        self, db: AsyncSession, user_entity_id: str, status: Optional[str] = "active"
    ) -> List[Contact]:
        """Get all contacts for a user"""
        query = select(Contact).where(Contact.user_entity_id == user_entity_id)

        if status:
            # Map string status to integer (assuming: active=1, inactive=2, blocked=3, deleted=4)
            status_map = {"active": 1, "inactive": 2, "blocked": 3, "deleted": 4}
            status_int = status_map.get(status, 1)
            query = query.where(Contact.status == status_int)

        query = query.order_by(desc(Contact.created_at))
        result = await db.execute(query)
        return result.scalars().all()

    async def get_user_contacts_with_profiles(
        self, db: AsyncSession, user_entity_id: str, status: Optional[str] = "active"
    ) -> List[Dict[str, Any]]:
        """Get user contacts with their social profiles"""
        contacts = await self.get_user_contacts(db, user_entity_id, status)

        contact_list = []
        for contact in contacts:
            # Get social profile for the contact
            profile_result = await db.execute(
                select(SocialProfile).where(SocialProfile.entity_id == contact.contact_entity_id)
            )
            profile = profile_result.scalar_one_or_none()

            contact_data = {
                "id": contact.contact_entity_id,  # Map to frontend expected field
                "contact_type": contact.contact_type,
                "status": self._map_status_to_string(contact.status),
                "added_at": contact.created_at,
                "last_interaction": contact.updated_at,
                "nickname": profile.nickname if profile else None,
                "avatar_url": profile.avatar_url if profile else None,
                "bio": profile.bio if profile else None,
            }
            contact_list.append(contact_data)

        return contact_list

    async def create_contact(
        self, db: AsyncSession, user_entity_id: str, contact_data: ContactCreate
    ) -> Contact:
        """Create a new contact relationship"""
        try:
            # Check if contact already exists
            existing = await self.get_contact_by_entities(
                db, user_entity_id, contact_data.contact_entity_id
            )
            if existing:
                raise ValueError("Contact relationship already exists")

            db_contact = Contact(
                user_entity_id=user_entity_id,
                contact_entity_id=contact_data.contact_entity_id,
                contact_type=contact_data.contact_type.value,
                status=1,  # active
            )

            db.add(db_contact)
            await db.commit()
            await db.refresh(db_contact)

            logger.info(
                "contact_created",
                user_entity_id=user_entity_id,
                contact_entity_id=contact_data.contact_entity_id,
                contact_type=contact_data.contact_type.value,
            )

            return db_contact

        except IntegrityError as e:
            await db.rollback()
            logger.error("contact_creation_integrity_error", error=str(e))
            raise ValueError("Failed to create contact due to database constraint")
        except Exception as e:
            await db.rollback()
            logger.error("contact_creation_error", error=str(e))
            raise

    async def update_contact(
        self, db: AsyncSession, contact_id: int, contact_update: ContactUpdate
    ) -> Optional[Contact]:
        """Update contact information"""
        contact = await self.get_contact_by_id(db, contact_id)
        if not contact:
            return None

        if contact_update.status:
            # Map string status to integer
            status_map = {"active": 1, "inactive": 2, "blocked": 3, "deleted": 4}
            contact.status = status_map.get(contact_update.status.value, 1)

        try:
            await db.commit()
            await db.refresh(contact)

            logger.info("contact_updated", contact_id=contact_id)
            return contact

        except Exception as e:
            await db.rollback()
            logger.error("contact_update_error", error=str(e), contact_id=contact_id)
            raise

    async def delete_contact(self, db: AsyncSession, contact_id: int) -> bool:
        """Soft delete a contact (set status to deleted)"""
        contact = await self.get_contact_by_id(db, contact_id)
        if not contact:
            return False

        contact.status = 4  # deleted

        try:
            await db.commit()
            logger.info("contact_deleted", contact_id=contact_id)
            return True
        except Exception as e:
            await db.rollback()
            logger.error("contact_deletion_error", error=str(e), contact_id=contact_id)
            return False

    async def get_contact_count(self, db: AsyncSession, user_entity_id: str) -> int:
        """Get total number of active contacts for a user"""
        result = await db.execute(
            select(func.count(Contact.id)).where(
                and_(Contact.user_entity_id == user_entity_id, Contact.status == 1)  # active
            )
        )
        return result.scalar() or 0

    async def get_user_contact_limits(self, db: AsyncSession, user_entity_id: str) -> Dict[str, Any]:
        """Get user's contact limits and current usage"""
        # Get user info for limits
        user_result = await db.execute(select(User).where(User.entity_id == user_entity_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User not found: {user_entity_id}")

        current_count = await self.get_contact_count(db, user_entity_id)

        return {
            "current_count": current_count,
            "limit": user.contact_limit,
            "remaining": max(0, user.contact_limit - current_count),
            "can_add_more": current_count < user.contact_limit,
        }

    def _map_status_to_string(self, status_int: int) -> str:
        """Map integer status to string"""
        status_map = {1: "active", 2: "inactive", 3: "blocked", 4: "deleted"}
        return status_map.get(status_int, "unknown")


# Create global instance
contact_crud = ContactCRUD()
