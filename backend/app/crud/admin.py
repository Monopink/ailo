"""
Admin management CRUD operations.

This module contains CRUD operations for admin users and operation logs.
"""

from typing import List, Optional
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBaseWithStatus, CRUDBase
from models.admin import AdminUser, AdminOperationLog, AdminLoginLog
from schemas.admin import AdminUserCreate, AdminUserUpdate, AdminOperationLogCreate
from enums import AdminRole


class CRUDAdminUser(CRUDBaseWithStatus[AdminUser, AdminUserCreate, AdminUserUpdate]):
    """CRUD operations for AdminUser model."""

    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[AdminUser]:
        """Get admin user by username."""
        result = await db.execute(select(self.model).where(self.model.username == username))
        return result.scalar_one_or_none()

    async def authenticate(self, db: AsyncSession, *, username: str, password: str) -> Optional[AdminUser]:
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
        return user.status == 1

    async def get_by_role(
        self, db: AsyncSession, *, role: AdminRole, skip: int = 0, limit: int = 100
    ) -> List[AdminUser]:
        """Get admin users by role."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.role == role, self.model.status == 1))
            .order_by(self.model.created_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_super_admins(self, db: AsyncSession) -> List[AdminUser]:
        """Get all super admin users."""
        result = await db.execute(
            select(self.model).where(and_(self.model.role == AdminRole.SUPER_ADMIN, self.model.status == 1))
        )
        return list(result.scalars().all())

    async def count_by_role(self, db: AsyncSession, *, role: AdminRole) -> int:
        """Count admin users by role."""
        result = await db.execute(
            select(func.count(self.model.id)).where(and_(self.model.role == role, self.model.status == 1))
        )
        return result.scalar()

    async def update_last_login(self, db: AsyncSession, *, user_id: int) -> Optional[AdminUser]:
        """Update admin user's last login time."""
        from datetime import datetime

        user = await self.get(db, id=user_id)
        if user:
            user.last_login = datetime.utcnow()
            user.login_count += 1
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    async def change_password(
        self, db: AsyncSession, *, user_id: int, new_password_hash: str
    ) -> Optional[AdminUser]:
        """Change admin user password."""
        user = await self.get(db, id=user_id)
        if user:
            user.password_hash = new_password_hash
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    async def search_admins(self, db: AsyncSession, *, query: str, limit: int = 20) -> List[AdminUser]:
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
    ) -> List[AdminOperationLog]:
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
    ) -> List[AdminOperationLog]:
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
    ) -> List[AdminOperationLog]:
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
        self, db: AsyncSession, *, resource_type: str, resource_id: str, skip: int = 0, limit: int = 50
    ) -> List[AdminOperationLog]:
        """Get operations for a specific resource."""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.resource_type == resource_type, self.model.resource_id == resource_id))
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_operations(
        self, db: AsyncSession, *, hours: int = 24, limit: int = 100
    ) -> List[AdminOperationLog]:
        """Get recent operations within specified hours."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(self.model)
            .where(self.model.created_at >= cutoff_time)
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_admin_operations(
        self, db: AsyncSession, *, admin_user_id: int, hours: Optional[int] = None
    ) -> int:
        """Count operations by admin user."""
        conditions = [self.model.admin_user_id == admin_user_id]

        if hours:
            from datetime import datetime, timedelta

            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            conditions.append(self.model.created_at >= cutoff_time)

        result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        return result.scalar()


class CRUDAdminLoginLog(CRUDBase[AdminLoginLog, dict, dict]):
    """CRUD operations for AdminLoginLog model."""

    async def get_admin_login_history(
        self, db: AsyncSession, *, admin_user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AdminLoginLog]:
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
    ) -> List[AdminLoginLog]:
        """Get recent failed login attempts for username."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
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
    ) -> List[AdminLoginLog]:
        """Get recent successful logins."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.result == 1, self.model.created_at >= cutoff_time))  # Success
            .order_by(desc(self.model.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_login_attempts(
        self, db: AsyncSession, *, username: str, hours: int = 24, result: Optional[int] = None
    ) -> int:
        """Count login attempts for username."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        conditions = [self.model.username == username, self.model.created_at >= cutoff_time]

        if result is not None:
            conditions.append(self.model.result == result)

        db_result = await db.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        return db_result.scalar()


# Create CRUD instances
admin_user = CRUDAdminUser(AdminUser)
admin_operation_log = CRUDAdminOperationLog(AdminOperationLog)
admin_login_log = CRUDAdminLoginLog(AdminLoginLog)
