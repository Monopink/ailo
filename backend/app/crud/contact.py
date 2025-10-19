"""
Contact management CRUD operations.

This module contains CRUD operations for contact relationships and requests.
"""

from typing import List, Optional
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.contact import Contact, ContactRequest
from schemas.contact import ContactCreate, ContactUpdate, ContactRequestCreate
from enums import ContactType, ContactRequestStatus


class CRUDContact(CRUDBase[Contact, ContactCreate, ContactUpdate]):
    """CRUD operations for Contact model."""

    async def get_by_conv_id(self, db: AsyncSession, *, conv_id: str) -> Optional[Contact]:
        """Get contact by conversation ID."""
        result = await db.execute(select(self.model).where(self.model.conv_id == conv_id))
        return result.scalar_one_or_none()

    async def get_user_contact(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str
    ) -> Optional[Contact]:
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
        contact_type: Optional[ContactType] = None,
        include_blocked: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Contact]:
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

    async def get_pinned_contacts(self, db: AsyncSession, *, user_qiao_id: str) -> List[Contact]:
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
    ) -> List[Contact]:
        """Search user's contacts by alias or contact info."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.user_qiao_id == user_qiao_id,
                    self.model.is_deleted == 0,
                    or_(
                        self.model.alias.ilike(f"%{query}%"), self.model.contact_qiao_id.ilike(f"%{query}%")
                    ),
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_user_contacts(
        self, db: AsyncSession, *, user_qiao_id: str, contact_type: Optional[ContactType] = None
    ) -> int:
        """Count user's contacts."""
        conditions = [self.model.user_qiao_id == user_qiao_id, self.model.is_deleted == 0]

        if contact_type:
            conditions.append(self.model.contact_type == contact_type)

        result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        count = result.scalar()
        return count if count is not None else 0

    async def create_with_user(
        self, db: AsyncSession, *, obj_in: ContactCreate, user_qiao_id: str, user_id: int, conv_id: str
    ) -> Contact:
        """Create contact with user information."""
        from utils.snowflake import generate_snowflake_id

        contact_data = {
            "id": generate_snowflake_id(),
            "conv_id": conv_id,
            "user_id": user_id,
            "user_qiao_id": user_qiao_id,
            "contact_type": obj_in.contact_type,
            "contact_id": 0,  # Will be set after querying contact
            "contact_qiao_id": obj_in.contact_qiao_id,
            "alias": obj_in.alias,
            "avatar_alias_url": obj_in.avatar_alias_url,
            "tags": obj_in.tags,
            "remark": obj_in.remark,
        }

        db_obj = self.model(**contact_data)
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def is_contact_exists(self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_id: str) -> bool:
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
    ) -> Optional[Contact]:
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

    async def batch_update_contacts(
        self, db: AsyncSession, *, user_qiao_id: str, contact_qiao_ids: List[str], update_data: dict
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


class CRUDContactRequest(CRUDBase[ContactRequest, ContactRequestCreate, dict]):
    """CRUD operations for ContactRequest model."""

    async def get_pending_request(
        self, db: AsyncSession, *, from_qiao_id: str, to_qiao_id: str
    ) -> Optional[ContactRequest]:
        """Get pending contact request between two users."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.from_qiao_id == from_qiao_id,
                    self.model.to_qiao_id == to_qiao_id,
                    self.model.status == ContactRequestStatus.PENDING,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_sent_requests(
        self,
        db: AsyncSession,
        *,
        from_qiao_id: str,
        status: Optional[ContactRequestStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ContactRequest]:
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
        status: Optional[ContactRequestStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ContactRequest]:
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
                and_(self.model.to_qiao_id == to_qiao_id, self.model.status == ContactRequestStatus.PENDING)
            )
        )
        count = result.scalar()
        return count if count is not None else 0

    async def update_request_status(
        self, db: AsyncSession, *, request_id: int, status: ContactRequestStatus
    ) -> Optional[ContactRequest]:
        """Update contact request status."""
        request = await self.get(db, id=request_id)
        if request:
            request.status = status
            db.add(request)
            await db.commit()
            await db.refresh(request)
        return request


# Create CRUD instances
contact = CRUDContact(Contact)
contact_request = CRUDContactRequest(ContactRequest)
