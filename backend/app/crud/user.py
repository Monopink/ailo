"""
User management CRUD operations.

This module contains CRUD operations for user accounts, sessions, and authentication.
"""

from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBaseWithQiaoId, CRUDBase
from models.user import User, UserSession, LoginRecord
from schemas.user import UserCreate, UserUpdate, SessionCreate
from enums import UserStatus, DeviceType


class CRUDUser(CRUDBaseWithQiaoId[User, UserCreate, UserUpdate]):
    """CRUD operations for User model."""

    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> Optional[User]:
        """Get user by phone number."""
        result = await db.execute(select(self.model).where(self.model.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await db.execute(select(self.model).where(self.model.email == email))
        return result.scalar_one_or_none()

    async def get_by_phone_or_email(
        self, db: AsyncSession, *, phone: Optional[str] = None, email: Optional[str] = None
    ) -> Optional[User]:
        """Get user by phone or email."""
        conditions = []
        if phone:
            conditions.append(self.model.phone == phone)
        if email:
            conditions.append(self.model.email == email)

        if not conditions:
            return None

        result = await db.execute(select(self.model).where(or_(*conditions)))
        return result.scalar_one_or_none()

    async def authenticate(
        self, db: AsyncSession, *, phone: Optional[str] = None, email: Optional[str] = None, password: str
    ) -> Optional[User]:
        """Authenticate user with phone/email and password."""
        user = await self.get_by_phone_or_email(db, phone=phone, email=email)
        if not user:
            return None
        # TODO: Implement password verification
        # if not verify_password(password, user.password_hash):
        #     return None
        return user

    async def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.status == UserStatus.ACTIVE

    async def get_active_users(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[User]:
        """Get active users with pagination."""
        result = await db.execute(
            select(self.model).where(self.model.status == UserStatus.ACTIVE).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def search_users(self, db: AsyncSession, *, query: str, limit: int = 20) -> List[User]:
        """Search users by username, phone, or email."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.status == UserStatus.ACTIVE,
                    or_(
                        self.model.username.ilike(f"%{query}%"),
                        self.model.phone.ilike(f"%{query}%"),
                        self.model.email.ilike(f"%{query}%"),
                    ),
                )
            )
            .limit(limit)
        )
        return list(result.scalars().all())


class CRUDUserSession(CRUDBase[UserSession, SessionCreate, dict]):
    """CRUD operations for UserSession model."""

    async def get_by_token(self, db: AsyncSession, *, token: str) -> Optional[UserSession]:
        """Get session by token."""
        result = await db.execute(select(self.model).where(self.model.session_token == token))
        return result.scalar_one_or_none()

    async def get_active_session(self, db: AsyncSession, *, token: str) -> Optional[UserSession]:
        """Get active session by token."""
        result = await db.execute(
            select(self.model).where(
                and_(self.model.session_token == token, self.model.is_active.is_(True))
            )
        )
        return result.scalar_one_or_none()

    async def get_user_sessions(
        self, db: AsyncSession, *, user_id: int, active_only: bool = True
    ) -> List[UserSession]:
        """Get user's sessions."""
        query = select(self.model).where(self.model.user_id == user_id)
        if active_only:
            query = query.where(self.model.is_active.is_(True))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_user_sessions_by_device(
        self, db: AsyncSession, *, user_id: int, device_type: DeviceType
    ) -> List[UserSession]:
        """Get user's sessions by device type."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_id == user_id,
                    self.model.device_type == device_type,
                    self.model.is_active.is_(True),
                )
            )
        )
        return list(result.scalars().all())

    async def deactivate_session(self, db: AsyncSession, *, token: str) -> Optional[UserSession]:
        """Deactivate a session."""
        session = await self.get_by_token(db, token=token)
        if session:
            session.is_active = False
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    async def deactivate_user_sessions(
        self, db: AsyncSession, *, user_id: int, exclude_token: Optional[str] = None
    ) -> int:
        """Deactivate all user sessions except the excluded one."""
        query = select(self.model).where(
            and_(self.model.user_id == user_id, self.model.is_active.is_(True))
        )
        if exclude_token:
            query = query.where(self.model.session_token != exclude_token)

        result = await db.execute(query)
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.is_active = False
            db.add(session)
            count += 1

        await db.commit()
        return count


class CRUDLoginRecord(CRUDBase[LoginRecord, dict, dict]):
    """CRUD operations for LoginRecord model."""

    async def get_user_login_history(
        self, db: AsyncSession, *, user_id: int, limit: int = 50
    ) -> List[LoginRecord]:
        """Get user's login history."""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_failed_attempts(
        self, db: AsyncSession, *, identifier: str, minutes: int = 15
    ) -> List[LoginRecord]:
        """Get recent failed login attempts for phone/email."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        result = await db.execute(
            select(self.model).where(
                and_(
                    or_(self.model.phone == identifier, self.model.email == identifier),
                    self.model.success.is_(False),
                    self.model.created_at >= cutoff_time,
                )
            )
        )
        return list(result.scalars().all())


# Create CRUD instances
user = CRUDUser(User)
user_session = CRUDUserSession(UserSession)
login_record = CRUDLoginRecord(LoginRecord)
