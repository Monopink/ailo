"""
Contact management CRUD operations.

This module contains CRUD operations for contact relationships and requests.
"""

from crud.base import CRUDBase
from enums import ContactRequestStatus, ContactType
from models.contact import Contact, ContactRequest
from schemas.contact import ContactCreate, ContactRequestCreate, ContactRequestUpdate, ContactUpdate
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.snowflake import generate_snowflake_id


class CRUDContact(CRUDBase[Contact, ContactCreate, ContactUpdate]):
    """CRUD operations for Contact model."""

    async def get_by_conv_id(self, db: AsyncSession, *, conv_id: str) -> Contact | None:
        """Get contact by conversation ID."""
        result = await db.execute(select(self.model).where(self.model.conv_id == conv_id))
        return result.scalar_one_or_none()

    async def get_user_contact(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str
    ) -> Contact | None:
        """Get specific contact relationship."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.contact_qiao_id == contact_qiao_id,
                    self.model.is_deleted == 0,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_contacts(
        self,
        db: AsyncSession,
        *,
        user_qiao_id: str,
        contact_type: ContactType | None = None,
        include_blocked: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get user's contacts with filtering."""
        conditions = [self.model.user_qiao_id == user_qiao_id, self.model.is_deleted == 0]

        if contact_type:
            conditions.append(self.model.contact_type == contact_type)

        if not include_blocked:
            conditions.append(self.model.is_blocked == 0)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.is_pinned.desc(), self.model.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pinned_contacts(self, db: AsyncSession, *, user_qiao_id: str) -> list[Contact]:
        """Get user's pinned contacts."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.is_pinned.is_(True),
                    self.model.is_deleted == 0,
                )
            )
            .order_by(self.model.updated_at.desc())
        )
        return list(result.scalars().all())

    async def search_user_contacts(
        self, db: AsyncSession, *, user_qiao_id: str, query: str, limit: int = 20
    ) -> list[Contact]:
        """Search user's contacts by alias or contact info."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.is_deleted == 0,
                    or_(
                        self.model.alias.ilike(f"%{query}%"),
                        self.model.contact_qiao_id.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_user_contacts(
        self, db: AsyncSession, *, user_qiao_id: str, contact_type: ContactType | None = None
    ) -> int:
        """Count user's contacts."""
        conditions = [self.model.user_qiao_id == user_qiao_id, self.model.is_deleted == 0]

        if contact_type:
            conditions.append(self.model.contact_type == contact_type)

        result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        count = result.scalar()
        return count if count is not None else 0

    async def create_with_user(
        self,
        db: AsyncSession,
        *,
        obj_in: ContactCreate,
        user_qiao_id: str,
        user_id: int,
        conv_id: str,
    ) -> Contact:
        """Create contact with user information."""
        tags_payload = {"tags": obj_in.tags} if obj_in.tags else None

        contact_data = {
            "id": generate_snowflake_id(),
            "conv_id": conv_id,
            "user_id": user_id,
            "user_qiao_id": user_qiao_id,
            "contact_type": obj_in.contact_type,
            "contact_id": 0,  # Will be set after querying contact
            "contact_qiao_id": obj_in.contact_qiao_id,
            "alias": obj_in.alias,
            "custom_avatar_url": obj_in.custom_avatar_url,
            "tags": tags_payload,
            "remark": obj_in.remark,
            "source": (obj_in.source or "unknown"),
        }

        db_obj = self.model(**contact_data)
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def is_contact_exists(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str
    ) -> bool:
        """Check if contact relationship exists."""
        result = await db.execute(
            select(func.count(self.model.id)).where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.contact_qiao_id == contact_qiao_id,
                    self.model.is_deleted == 0,
                )
            )
        )
        count = result.scalar()
        return (count if count is not None else 0) > 0

    async def soft_delete_contact(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str
    ) -> Contact | None:
        """Soft delete a contact relationship."""
        contact = await self.get_user_contact(
            db, user_qiao_id=user_qiao_id, contact_qiao_id=contact_qiao_id
        )
        if contact:
            contact.is_deleted = True
            db.add(contact)
            await db.commit()
            await db.refresh(contact)
        return contact

    async def get_user_contact_including_deleted(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str
    ) -> Contact | None:
        """
        Get contact including deleted ones.

        Used for checking if a deleted contact exists before re-adding.

        Args:
            db: Database session
            user_qiao_id: User's qiao_id
            contact_qiao_id: Contact's qiao_id

        Returns:
            Contact record or None if not found
        """
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.contact_qiao_id == contact_qiao_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def restore_contact(
        self,
        db: AsyncSession,
        *,
        contact: Contact,
        alias: str | None = None,
        tags: dict | None = None,
    ) -> Contact:
        """
        Restore a soft-deleted contact with new settings.

        Strategy: Do not preserve old settings (alias, tags, remark).

        Args:
            db: Database session
            contact: Contact object to restore
            alias: New alias (optional)
            tags: New tags (optional)

        Returns:
            Restored contact
        """
        contact.is_deleted = 0
        contact.deleted_at = None
        contact.alias = alias
        contact.tags = tags
        contact.remark = None  # Reset remark

        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return contact

    async def batch_update_contacts(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_ids: list[str], update_data: dict
    ) -> int:
        """Batch update contacts."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.contact_qiao_id.in_(contact_qiao_ids),
                    self.model.is_deleted == 0,
                )
            )
        )
        contacts = result.scalars().all()

        count = 0
        for contact in contacts:
            for field, value in update_data.items():
                if hasattr(contact, field):
                    setattr(contact, field, value)
            db.add(contact)
            count += 1

        await db.commit()
        return count


class CRUDContactRequest(CRUDBase[ContactRequest, ContactRequestCreate, ContactRequestUpdate]):
    """CRUD operations for ContactRequest model."""

    async def get_latest_request(
        self, db: AsyncSession, *, from_qiao_id: str, to_qiao_id: str
    ) -> ContactRequest | None:
        """Get the latest contact request between two parties regardless of status."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.from_qiao_id == from_qiao_id,
                    self.model.to_qiao_id == to_qiao_id,
                )
            )
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_pending_request(
        self, db: AsyncSession, *, from_qiao_id: str, to_qiao_id: str
    ) -> ContactRequest | None:
        """Get pending or processing contact request between two users. Returns the most recent one if multiple exist."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.from_qiao_id == from_qiao_id,
                    self.model.to_qiao_id == to_qiao_id,
                    self.model.status.in_(
                        [ContactRequestStatus.PENDING, ContactRequestStatus.PROCESSING]
                    ),
                )
            )
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_user_sent_requests(
        self,
        db: AsyncSession,
        *,
        from_qiao_id: str,
        status: ContactRequestStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContactRequest]:
        """Get user's sent contact requests."""
        conditions = [self.model.from_qiao_id == from_qiao_id]
        if status:
            conditions.append(self.model.status == status)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_received_requests(
        self,
        db: AsyncSession,
        *,
        to_qiao_id: str,
        status: ContactRequestStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ContactRequest]:
        """Get user's received contact requests."""
        conditions = [self.model.to_qiao_id == to_qiao_id]
        if status:
            conditions.append(self.model.status == status)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_pending_requests(self, db: AsyncSession, *, to_qiao_id: str) -> int:
        """Count pending requests for a user."""
        result = await db.execute(
            select(func.count(self.model.id)).where(
                and_(
                    self.model.to_qiao_id == to_qiao_id,
                    self.model.status == ContactRequestStatus.PENDING,
                )
            )
        )
        count = result.scalar()
        return count if count is not None else 0

    async def update_request_status(
        self, db: AsyncSession, *, request_id: int, status: ContactRequestStatus
    ) -> ContactRequest | None:
        """Update contact request status."""
        request = await self.get(db, id=request_id)
        if request:
            request.status = status
            db.add(request)
            await db.commit()
            await db.refresh(request)
        return request

    async def get_for_update(self, db: AsyncSession, *, request_id: int) -> ContactRequest | None:
        """Fetch a contact request row with FOR UPDATE locking."""
        result = await db.execute(
            select(self.model).where(self.model.id == request_id).with_for_update()
        )
        return result.scalar_one_or_none()


# Create CRUD instances
contact = CRUDContact(Contact)
contact_request = CRUDContactRequest(ContactRequest)
