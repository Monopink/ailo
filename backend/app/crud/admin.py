"""
Admin management CRUD operations.

This module contains CRUD operations for admin users and operation logs.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase, CRUDBaseWithStatus
from app.enums import AdminRole, AdminStatus
from app.models.admin import AdminLoginLog, AdminOperationLog, AdminUser
from app.schemas.admin import AdminOperationLogCreate, AdminUserCreate, AdminUserUpdate


class CRUDAdminUser(CRUDBaseWithStatus[AdminUser, AdminUserCreate, AdminUserUpdate]):
    """CRUD operations for AdminUser model."""

    async def get_by_username(self, db: AsyncSession, *, username: str) -> AdminUser | None:
        """Get admin user by username."""
        result = await db.execute(select(self.model).where(self.model.username == username))
        return result.scalar_one_or_none()

    async def authenticate(
        self, db: AsyncSession, *, username: str, password: str
    ) -> AdminUser | None:
        """Authenticate admin user."""
        user = await self.get_by_username(db, username=username)
        if not user:
            return None
        # TODO: Implement password verification
        # if not verify_password(password, user.password_hash):
        #     return None
        return user

    async def is_active(self, user: AdminUser) -> bool:
        """Check if admin user is active."""
        return user.status == AdminStatus.ACTIVE  # Use enum instead of hardcoded value

    async def get_by_role(
        self, db: AsyncSession, *, role: AdminRole, skip: int = 0, limit: int = 100
    ) -> list[AdminUser]:
        """Get admin users by role."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(self.model.role == role, self.model.status == AdminStatus.ACTIVE)
            )  # Use enum
            .order_by(self.model.created_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_super_admins(self, db: AsyncSession) -> list[AdminUser]:
        """Get all super admin users."""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.role == AdminRole.SUPER_ADMIN,
                    self.model.status == AdminStatus.ACTIVE,
                )
            )  # Use enum
        )
        return list(result.scalars().all())

    async def count_by_role(self, db: AsyncSession, *, role: AdminRole) -> int:
        """Count admin users by role."""
        result = await db.execute(
            select(func.count(self.model.id)).where(
                and_(self.model.role == role, self.model.status == 1)
            )
        )
        return result.scalar()

    async def update_last_login(self, db: AsyncSession, *, user_id: int) -> AdminUser | None:
        """Update admin user's last login time."""

        user = await self.get(db, id=user_id)
        if user:
            user.last_login = datetime.now(UTC)
            user.login_count += 1
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    async def change_password(
        self, db: AsyncSession, *, user_id: int, new_password_hash: str
    ) -> AdminUser | None:
        """Change admin user password."""
        user = await self.get(db, id=user_id)
        if user:
            user.password_hash = new_password_hash
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    async def search_admins(
        self, db: AsyncSession, *, query: str, limit: int = 20
    ) -> list[AdminUser]:
        """Search admin users by username."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.username.ilike(f"%{query}%"), self.model.status == 1))
            .limit(limit)
        )
        return list(result.scalars().all())


class CRUDAdminOperationLog(CRUDBase[AdminOperationLog, AdminOperationLogCreate, dict]):
    """CRUD operations for AdminOperationLog model."""

    async def get_admin_operations(
        self, db: AsyncSession, *, admin_user_id: int, skip: int = 0, limit: int = 100
    ) -> list[AdminOperationLog]:
        """Get operations by admin user."""
        result = await db.execute(
            select(self.model)
            .where(self.model.admin_user_id == admin_user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_resource_type(
        self, db: AsyncSession, *, resource_type: str, skip: int = 0, limit: int = 100
    ) -> list[AdminOperationLog]:
        """Get operations by resource type."""
        result = await db.execute(
            select(self.model)
            .where(self.model.resource_type == resource_type)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_operation_type(
        self, db: AsyncSession, *, operation_type: int, skip: int = 0, limit: int = 100
    ) -> list[AdminOperationLog]:
        """Get operations by operation type."""
        result = await db.execute(
            select(self.model)
            .where(self.model.operation_type == operation_type)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_resource_operations(
        self,
        db: AsyncSession,
        *,
        resource_type: str,
        resource_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AdminOperationLog]:
        """Get operations for a specific resource."""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.resource_type == resource_type, self.model.resource_id == resource_id
                )
            )
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_operations(
        self, db: AsyncSession, *, hours: int = 24, limit: int = 100
    ) -> list[AdminOperationLog]:
        """Get recent operations within specified hours."""

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        result = await db.execute(
            select(self.model)
            .where(self.model.created_at >= cutoff_time)
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_admin_operations(
        self, db: AsyncSession, *, admin_user_id: int, hours: int | None = None
    ) -> int:
        """Count operations by admin user."""
        conditions = [self.model.admin_user_id == admin_user_id]

        if hours:
            cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
            conditions.append(self.model.created_at >= cutoff_time)

        result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        return result.scalar()


class CRUDAdminLoginLog(CRUDBase[AdminLoginLog, dict, dict]):
    """CRUD operations for AdminLoginLog model."""

    async def get_admin_login_history(
        self, db: AsyncSession, *, admin_user_id: int, skip: int = 0, limit: int = 100
    ) -> list[AdminLoginLog]:
        """Get admin user's login history."""
        result = await db.execute(
            select(self.model)
            .where(self.model.admin_user_id == admin_user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_login_attempts(
        self, db: AsyncSession, *, username: str, hours: int = 1
    ) -> list[AdminLoginLog]:
        """Get recent failed login attempts for username."""

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.username == username,
                    self.model.result == 2,  # Failed
                    self.model.created_at >= cutoff_time,
                )
            )
            .order_by(desc(self.model.created_at))
        )
        return list(result.scalars().all())

    async def get_successful_logins(
        self, db: AsyncSession, *, hours: int = 24, limit: int = 100
    ) -> list[AdminLoginLog]:
        """Get recent successful logins."""

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.result == 1, self.model.created_at >= cutoff_time))  # Success
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_login_attempts(
        self, db: AsyncSession, *, username: str, hours: int = 24, result: int | None = None
    ) -> int:
        """Count login attempts for username."""

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        conditions = [self.model.username == username, self.model.created_at >= cutoff_time]

        if result is not None:
            conditions.append(self.model.result == result)

        db_result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        return db_result.scalar()


# Create CRUD instances
admin_user = CRUDAdminUser(AdminUser)
admin_operation_log = CRUDAdminOperationLog(AdminOperationLog)
admin_login_log = CRUDAdminLoginLog(AdminLoginLog)
