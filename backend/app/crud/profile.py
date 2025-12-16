"""
Profile CRUD operations
"""

from typing import Any

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import ProfileOwnerType
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


class CRUDProfile(CRUDBase[Profile, ProfileCreate, ProfileUpdate]):
    """Profile CRUD operations"""

    async def get_by_owner(
        self, db: AsyncSession, *, owner_id: int, owner_type: ProfileOwnerType
    ) -> Profile | None:
        """Get profile by owner ID and type"""
        try:
            stmt = select(self.model).where(
                and_(self.model.owner_id == owner_id, self.model.owner_type == owner_type)
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                "get_profile_by_owner_error", error=str(e), owner_id=owner_id, owner_type=owner_type
            )
            raise

    async def get_by_owner_qiao_id(
        self,
        db: AsyncSession,
        *,
        owner_qiao_id: str,
    ) -> Profile | None:
        """Get profile by owner qiao_id.

        Note: qiao_id is globally unique across all entity types,
        so owner_type is not needed for lookup.
        """
        try:
            stmt = select(self.model).where(self.model.owner_qiao_id == owner_qiao_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception:
            logger.error(
                "get_profile_by_owner_qiao_id_error",
                owner_qiao_id=owner_qiao_id,
            )
            raise

    async def create_with_owner(
        self,
        db: AsyncSession,
        *,
        obj_in: ProfileCreate,
        owner_id: int,
        owner_qiao_id: str,
        owner_type: ProfileOwnerType,
        commit: bool = True,
    ) -> Profile:
        """Create profile with owner information"""
        try:
            obj_data = obj_in.model_dump(exclude_unset=True)
            obj_data["owner_id"] = owner_id
            obj_data["owner_qiao_id"] = owner_qiao_id
            obj_data["owner_type"] = owner_type

            obj_data["id"] = generate_snowflake_id()

            db_obj = self.model(**obj_data)
            db.add(db_obj)
            if commit:
                await db.commit()
                await db.refresh(db_obj)
            else:
                await db.flush()
            logger.info(
                "profile_created",
                profile_id=db_obj.id,
                owner_id=owner_id,
                owner_qiao_id=owner_qiao_id,
                owner_type=owner_type,
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                "create_profile_error",
                error=str(e),
                owner_id=owner_id,
                owner_qiao_id=owner_qiao_id,
                owner_type=owner_type,
            )
            raise
        else:
            return db_obj

    async def update_by_owner(
        self,
        db: AsyncSession,
        *,
        owner_id: int,
        owner_type: ProfileOwnerType,
        obj_in: ProfileUpdate,
        commit: bool = True,
    ) -> Profile | None:
        """Update profile by owner ID and type"""
        try:
            # Get existing profile
            db_obj = await self.get_by_owner(db, owner_id=owner_id, owner_type=owner_type)
            if not db_obj:
                return None

            # Update profile
            update_data = obj_in.model_dump(exclude_unset=True)
            if update_data:
                if commit:
                    stmt = (
                        update(self.model)
                        .where(
                            and_(
                                self.model.owner_id == owner_id, self.model.owner_type == owner_type
                            )
                        )
                        .values(**update_data)
                    )
                    await db.execute(stmt)
                    await db.commit()
                    await db.refresh(db_obj)
                else:
                    for k, v in update_data.items():
                        setattr(db_obj, k, v)
                    db.add(db_obj)
                    await db.flush()
                logger.info(
                    "profile_updated",
                    profile_id=db_obj.id,
                    owner_id=owner_id,
                    owner_type=owner_type,
                )
        except Exception as e:
            if commit:
                await db.rollback()
            logger.error(
                "update_profile_error", error=str(e), owner_id=owner_id, owner_type=owner_type
            )
            raise
        else:
            return db_obj

    async def delete_by_owner(
        self, db: AsyncSession, *, owner_id: int, owner_type: ProfileOwnerType
    ) -> bool:
        """Delete profile by owner ID and type"""
        try:
            stmt = delete(self.model).where(
                and_(self.model.owner_id == owner_id, self.model.owner_type == owner_type)
            )
            result = await db.execute(stmt)
            await db.commit()

            deleted: bool = result.rowcount > 0
            if deleted:
                logger.info("profile_deleted", owner_id=owner_id, owner_type=owner_type)
        except Exception as e:
            await db.rollback()
            logger.error(
                "delete_profile_error", error=str(e), owner_id=owner_id, owner_type=owner_type
            )
            raise
        else:
            return deleted

    async def get_profiles_by_gender(
        self, db: AsyncSession, gender: str, skip: int = 0, limit: int = 100
    ) -> list[Profile]:
        """Get profiles by gender"""
        try:
            stmt = select(self.model).where(self.model.gender == gender).offset(skip).limit(limit)
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("get_profiles_by_gender_error", error=str(e), gender=gender)
            raise

    async def get_profiles_by_age_range(
        self,
        db: AsyncSession,
        min_age: int | None = None,
        max_age: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Profile]:
        """Get profiles by age range - DEPRECATED: age field does not exist in Profile model"""
        raise NotImplementedError("age field does not exist in Profile model")

    async def search_profiles(
        self,
        db: AsyncSession,
        *,
        nickname: str | None = None,
        bio: str | None = None,
        gender: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Profile]:
        """Search profiles with multiple criteria"""
        try:
            stmt = select(self.model)

            if nickname:
                stmt = stmt.where(self.model.nickname.ilike(f"%{nickname}%"))
            if bio:
                stmt = stmt.where(self.model.bio.ilike(f"%{bio}%"))
            if gender:
                stmt = stmt.where(self.model.gender == gender)

            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("search_profiles_error", error=str(e))
            raise

    async def get_profile_stats(self, db: AsyncSession) -> dict[str, Any]:
        """Get profile statistics"""
        try:
            # Total profiles
            total_stmt = select(func.count(self.model.id))
            total_result = await db.execute(total_stmt)
            total_profiles = total_result.scalar()

            # Gender distribution
            gender_stmt = select(self.model.gender, func.count(self.model.id)).group_by(
                self.model.gender
            )
            gender_result = await db.execute(gender_stmt)
            # Convert Row objects to dict: gender (int | None) -> count (int)
            gender_distribution: dict[int | None, int] = {
                row[0]: row[1] for row in gender_result.all()
            }
        except Exception as e:
            logger.error("get_profile_stats_error", error=str(e))
            raise
        else:
            return {
                "total_profiles": total_profiles,
                "gender_distribution": gender_distribution,
            }


# Create instance
profile = CRUDProfile(Profile)
