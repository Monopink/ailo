"""
Profile CRUD operations
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.profile import Profile
from schemas.profile import ProfileCreate, ProfileUpdate
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDProfile(CRUDBase[Profile, ProfileCreate, ProfileUpdate]):
    """Profile CRUD operations"""

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> Optional[Profile]:
        """Get profile by user ID"""
        try:
            stmt = select(self.model).where(self.model.user_id == user_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("get_profile_by_user_id_error", error=str(e), user_id=user_id)
            raise

    async def create_with_user_id(
        self, db: AsyncSession, *, obj_in: ProfileCreate, user_id: int
    ) -> Profile:
        """Create profile with user ID"""
        try:
            obj_data = obj_in.model_dump()
            obj_data["user_id"] = user_id
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            logger.info("profile_created", profile_id=db_obj.id, user_id=user_id)
            return db_obj
        except Exception as e:
            await db.rollback()
            logger.error("create_profile_error", error=str(e), user_id=user_id)
            raise

    async def update_by_user_id(
        self, db: AsyncSession, *, user_id: int, obj_in: ProfileUpdate
    ) -> Optional[Profile]:
        """Update profile by user ID"""
        try:
            # Get existing profile
            db_obj = await self.get_by_user_id(db, user_id=user_id)
            if not db_obj:
                return None

            # Update profile
            update_data = obj_in.model_dump(exclude_unset=True)
            if update_data:
                stmt = update(self.model).where(self.model.user_id == user_id).values(**update_data)
                await db.execute(stmt)
                await db.commit()
                await db.refresh(db_obj)
                logger.info("profile_updated", profile_id=db_obj.id, user_id=user_id)

            return db_obj
        except Exception as e:
            await db.rollback()
            logger.error("update_profile_error", error=str(e), user_id=user_id)
            raise

    async def delete_by_user_id(self, db: AsyncSession, user_id: int) -> bool:
        """Delete profile by user ID"""
        try:
            stmt = delete(self.model).where(self.model.user_id == user_id)
            result = await db.execute(stmt)
            await db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info("profile_deleted", user_id=user_id)

            return deleted
        except Exception as e:
            await db.rollback()
            logger.error("delete_profile_error", error=str(e), user_id=user_id)
            raise

    async def get_profiles_by_gender(
        self, db: AsyncSession, gender: str, skip: int = 0, limit: int = 100
    ) -> List[Profile]:
        """Get profiles by gender"""
        try:
            stmt = select(self.model).where(self.model.gender == gender).offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error("get_profiles_by_gender_error", error=str(e), gender=gender)
            raise

    async def get_profiles_by_age_range(
        self,
        db: AsyncSession,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Profile]:
        """Get profiles by age range"""
        try:
            stmt = select(self.model)

            if min_age is not None:
                stmt = stmt.where(self.model.age >= min_age)
            if max_age is not None:
                stmt = stmt.where(self.model.age <= max_age)

            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error("get_profiles_by_age_range_error", error=str(e), min_age=min_age, max_age=max_age)
            raise

    async def search_profiles(
        self,
        db: AsyncSession,
        *,
        nickname: Optional[str] = None,
        bio: Optional[str] = None,
        gender: Optional[str] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Profile]:
        """Search profiles with multiple criteria"""
        try:
            stmt = select(self.model)

            if nickname:
                stmt = stmt.where(self.model.nickname.ilike(f"%{nickname}%"))
            if bio:
                stmt = stmt.where(self.model.bio.ilike(f"%{bio}%"))
            if gender:
                stmt = stmt.where(self.model.gender == gender)
            if min_age is not None:
                stmt = stmt.where(self.model.age >= min_age)
            if max_age is not None:
                stmt = stmt.where(self.model.age <= max_age)

            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error("search_profiles_error", error=str(e))
            raise

    async def get_profile_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get profile statistics"""
        try:
            from sqlalchemy import func

            # Total profiles
            total_stmt = select(func.count(self.model.id))
            total_result = await db.execute(total_stmt)
            total_profiles = total_result.scalar()

            # Gender distribution
            gender_stmt = select(self.model.gender, func.count(self.model.id)).group_by(self.model.gender)
            gender_result = await db.execute(gender_stmt)
            gender_distribution = dict(gender_result.all())

            # Age statistics
            age_stmt = select(
                func.min(self.model.age), func.max(self.model.age), func.avg(self.model.age)
            ).where(self.model.age.is_not(None))
            age_result = await db.execute(age_stmt)
            age_stats = age_result.first()

            return {
                "total_profiles": total_profiles,
                "gender_distribution": gender_distribution,
                "age_stats": {
                    "min_age": age_stats[0] if age_stats else None,
                    "max_age": age_stats[1] if age_stats else None,
                    "avg_age": float(age_stats[2]) if age_stats and age_stats[2] else None,
                },
            }
        except Exception as e:
            logger.error("get_profile_stats_error", error=str(e))
            raise


# Create instance
profile = CRUDProfile(Profile)
