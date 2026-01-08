"""AI instance CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI instance management.
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import AIInstanceCreator, ContactType
from app.models.ai import AIInstance
from app.models.contact import Contact
from app.schemas.ai import AIInstanceCreate, AIInstanceUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIInstance(CRUDBase[AIInstance, AIInstanceCreate, AIInstanceUpdate]):
    """AI instance CRUD operations with usage tracking."""

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> AIInstance | None:
        """Get instance by qiao_id.

        Args:
            db: Database session
            qiao_id: Instance qiao_id

        Returns:
            Instance object or None if not found

        """
        try:
            result = await db.execute(select(AIInstance).where(AIInstance.qiao_id == qiao_id))
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("instance_get_by_qiao_id_failed", error=str(e), qiao_id=qiao_id)
            raise RuntimeError(f"Failed to get instance by qiao_id: {e!s}")

    # Complex queries moved to services/ai/data layer for better separation of concerns

    async def get_user_instances(
        self, db: AsyncSession, *, user_qiao_id: str, skip: int = 0, limit: int = 100
    ) -> list[AIInstance]:
        """Get instances belonging to a specific user.

        Args:
            db: Database session
            user_qiao_id: User's qiao_id
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of instances

        """
        try:
            result = await db.execute(
                select(AIInstance)
                .join(Contact, Contact.contact_qiao_id == AIInstance.qiao_id)
                .where(
                    Contact.user_qiao_id == user_qiao_id,
                    Contact.contact_type == ContactType.AI,
                    Contact.is_deleted == 0,
                )
                .order_by(desc(AIInstance.created_at))
                .offset(skip)
                .limit(limit)
            )

            instances = list(result.scalars().all())

            logger.debug(
                "user_instances_retrieved", user_qiao_id=user_qiao_id, count=len(instances)
            )

            return instances

        except Exception as e:
            logger.error("user_instances_query_failed", error=str(e), user_qiao_id=user_qiao_id)
            # Non-fatal error: return empty list
            return []

    async def create(
        self, db: AsyncSession, *, obj_in: AIInstanceCreate, commit: bool = True
    ) -> AIInstance:
        """Create a new AI instance and update usage counts.

        Args:
            db: Database session
            obj_in: Instance creation schema
            commit: Whether to commit the transaction after creation

        Returns:
            Created instance object

        Raises:
            Exception: If creation or usage tracking fails

        """
        try:
            # Map schema fields to model fields to avoid invalid kwargs
            payload = obj_in.model_dump()
            creation_metadata_override = payload.pop("creation_metadata", None)
            metadata_snapshot = payload.copy()
            data = payload.copy()
            # placeholder_overrides -> prompt_variables
            if "placeholder_overrides" in data:
                data["prompt_variables"] = data.pop("placeholder_overrides")
            # Remove schema-only fields not present in model
            data.pop("position_mapping_coefficient", None)
            # Ensure created_by exists (DB requires non-null)
            data.setdefault("created_by", int(AIInstanceCreator.USER))
            creation_metadata = creation_metadata_override or metadata_snapshot
            data["creation_metadata"] = creation_metadata

            # Create instance explicitly (bypass base create for field mapping)
            db_obj = AIInstance(**data)
            db.add(db_obj)
            if commit:
                await db.commit()
                await db.refresh(db_obj)
            else:
                # Inside outer transaction: flush to get PKs without closing transaction
                await db.flush()
            instance = db_obj

            # Update usage counts for personality and style
            logger.info(
                "instance_created",
                instance_id=instance.id,
                personality_id=instance.personality_id,
                style_id=instance.style_id,
            )

            return instance

        except Exception as e:
            logger.error("instance_creation_failed", error=str(e))
            raise

    async def remove(self, db: AsyncSession, *, record_id: object) -> AIInstance | None:
        """Remove an AI instance and update usage counts.

        Args:
            db: Database session
            record_id: Instance ID

        Returns:
            Removed instance or None if not found

        Raises:
            Exception: If removal or usage tracking fails

        """
        try:
            # Get instance first to access personality_id and style_id
            instance = await self.get(db, record_id=record_id)

            if not instance:
                logger.warning("instance_not_found_for_removal", instance_id=record_id)
                return None

            personality_id = instance.personality_id
            style_id = instance.style_id

            # Remove instance using base class method
            removed_instance = await super().remove(db, record_id=record_id)

            logger.info(
                "instance_removed",
                instance_id=record_id,
                personality_id=personality_id,
                style_id=style_id,
            )

            return removed_instance

        except Exception as e:
            logger.error(
                "instance_removal_failed",
                error=str(e),
                instance_id=record_id,
            )
            raise


ai_instance = CRUDAIInstance(AIInstance)
