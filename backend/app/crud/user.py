"""
User management CRUD operations.

This module contains CRUD operations for user accounts, tokens, and authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from core.security import verify_password
from crud.base import CRUDBase, CRUDBaseWithQiaoId, ImmutableCRUDBase
from enums import AuthType, DeviceType, LoginResult, UserStatus
from models.user import LoginRecord, User, UserAuth, UserToken
from schemas.user import (
    LoginRecordCreate,
    TokenCreate,
    TokenUpdate,
    UserAuthCreate,
    UserAuthUpdate,
    UserCreate,
    UserUpdate,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.snowflake import generate_snowflake_id


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

    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        """Get user by username."""
        result = await db.execute(select(self.model).where(self.model.username == username))
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

        password_hash = user.password_hash
        if password_hash is None:
            return None
        if not verify_password(password, password_hash):
            return None
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


class CRUDUserToken(CRUDBase[UserToken, TokenCreate, TokenUpdate]):
    """CRUD operations for UserToken model."""

    async def get_by_token(self, db: AsyncSession, *, token: str) -> Optional[UserToken]:
        """Get token by token string."""
        result = await db.execute(select(self.model).where(self.model.token == token))
        return result.scalar_one_or_none()

    async def get_active_token(self, db: AsyncSession, *, token: str) -> Optional[UserToken]:
        """Get active token by token string."""
        result = await db.execute(
            select(self.model).where(and_(self.model.token == token, self.model.status == 1))
        )
        return result.scalar_one_or_none()

    async def get_user_tokens(
        self, db: AsyncSession, *, user_id: int, active_only: bool = True
    ) -> List[UserToken]:
        """Get user's tokens."""
        query = select(self.model).where(self.model.user_id == user_id)
        if active_only:
            query = query.where(self.model.status == 1)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_user_tokens_by_device(
        self, db: AsyncSession, *, user_id: int, device_type: DeviceType
    ) -> List[UserToken]:
        """Get user's tokens by device type."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_id == user_id,
                    self.model.device_type == device_type,
                    self.model.status == 1,
                )
            )
        )
        return list(result.scalars().all())

    async def revoke_token(self, db: AsyncSession, *, token: str) -> Optional[UserToken]:
        """Revoke a token."""

        user_token = await self.get_by_token(db, token=token)
        if user_token:
            user_token.status = 2
            user_token.revoked_at = datetime.now(timezone.utc)
            db.add(user_token)
            await db.commit()
            await db.refresh(user_token)
        return user_token

    async def revoke_user_tokens(
        self, db: AsyncSession, *, user_id: int, exclude_token: Optional[str] = None
    ) -> int:
        """Revoke all user tokens except the excluded one."""

        query = select(self.model).where(and_(self.model.user_id == user_id, self.model.status == 1))
        if exclude_token:
            query = query.where(self.model.token != exclude_token)

        result = await db.execute(query)
        tokens = result.scalars().all()

        count = 0
        revoked_at = datetime.now(timezone.utc)
        for user_token in tokens:
            user_token.status = 2
            user_token.revoked_at = revoked_at
            db.add(user_token)
            count += 1

        await db.commit()
        return count

    async def revoke_user_tokens_by_device(
        self, db: AsyncSession, *, user_id: int, device_type: DeviceType
    ) -> int:
        """Revoke all user tokens for a specific device type."""

        query = select(self.model).where(
            and_(
                self.model.user_id == user_id, self.model.device_type == device_type, self.model.status == 1
            )
        )

        result = await db.execute(query)
        tokens = result.scalars().all()

        count = 0
        revoked_at = datetime.now(timezone.utc)
        for user_token in tokens:
            user_token.status = 2
            user_token.revoked_at = revoked_at
            db.add(user_token)
            count += 1

        await db.commit()
        return count


class CRUDLoginRecord(ImmutableCRUDBase[LoginRecord, LoginRecordCreate]):
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

        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(self.model)
            .join(User, self.model.user_id == User.id)
            .where(
                and_(
                    or_(User.phone == identifier, User.email == identifier),
                    self.model.result == LoginResult.FAIL,
                    self.model.created_at >= cutoff_time,
                )
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# Create CRUD instances
user = CRUDUser(User)
user_token = CRUDUserToken(UserToken)
login_record = CRUDLoginRecord(LoginRecord)


class CRUDUserAuth(CRUDBase[UserAuth, UserAuthCreate, UserAuthUpdate]):
    """CRUD operations for UserAuth model (third-party identity bindings)."""

    async def get_by_provider_uid(
        self, db: AsyncSession, *, auth_type: AuthType | int, provider_uid: str
    ) -> Optional[UserAuth]:
        result = await db.execute(
            select(self.model).where(
                and_(self.model.auth_type == int(auth_type), self.model.provider_uid == provider_uid)
            )
        )
        return result.scalar_one_or_none()

    async def create_binding(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        user_qiao_id: str,
        auth_type: AuthType | int,
        provider_uid: str,
        unionid: Optional[str] = None,
        app_id: Optional[str] = None,
        extra_data: Optional[dict] = None,
    ) -> UserAuth:

        binding = self.model(
            id=generate_snowflake_id(),
            user_id=user_id,
            user_qiao_id=user_qiao_id,
            auth_type=int(auth_type),
            provider_uid=provider_uid,
            unionid=unionid,
            app_id=app_id,
            extra_data=extra_data,
            status=1,
        )
        db.add(binding)
        await db.commit()
        await db.refresh(binding)
        return binding


user_auth = CRUDUserAuth(UserAuth)
