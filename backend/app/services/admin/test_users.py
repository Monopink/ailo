"""
Test user management service for AI character testing.

This module provides functionality to manage test users (user_type=3)
specifically for AI character testing in the admin panel.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from models.user import User
from models.profile import Profile
from utils.logging import get_logger

logger = get_logger(__name__)


class TestUserService:
    """Service for managing test users for AI character testing."""

    def __init__(self):
        """Initialize the test user service."""
        pass

    async def get_test_users(self, db: AsyncSession, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all test users (user_type=3).

        Args:
            db: Database session
            active_only: Only return active users (status=1)

        Returns:
            List of test user dictionaries
        """
        try:
            # Build query with LEFT JOIN to get profile data
            query = (
                select(User, Profile)
                .outerjoin(
                    Profile,
                    and_(
                        Profile.owner_qiao_id == User.qiao_id,
                        Profile.owner_type == 1,  # ProfileOwnerType.USER
                    ),
                )
                .where(User.user_type == 3)
            )

            if active_only:
                query = query.where(User.status == 1)

            query = query.order_by(User.qiao_id)

            result = await db.execute(query)
            rows = result.all()

            test_users = []
            for user, profile in rows:
                test_users.append(
                    {
                        "id": user.id,
                        "qiao_id": user.qiao_id,
                        "nickname": profile.nickname if profile else None,
                        "phone": user.phone,
                        "status": user.status,
                        "user_type": user.user_type,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                )

            logger.debug(
                "test_users_retrieved",
                count=len(test_users),
                active_only=active_only,
            )

            return test_users

        except Exception as e:
            logger.error(
                "test_users_retrieval_failed",
                error=str(e),
                active_only=active_only,
            )
            return []

    async def get_test_user_by_qiao_id(self, db: AsyncSession, qiao_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific test user by qiao_id.

        Args:
            db: Database session
            qiao_id: User's qiao_id

        Returns:
            Test user dictionary or None if not found
        """
        try:
            result = await db.execute(
                select(User, Profile)
                .outerjoin(
                    Profile,
                    and_(
                        Profile.owner_qiao_id == User.qiao_id,
                        Profile.owner_type == 1,  # ProfileOwnerType.USER
                    ),
                )
                .where(and_(User.qiao_id == qiao_id, User.user_type == 3))
            )
            row = result.first()

            if not row:
                logger.warning(
                    "test_user_not_found",
                    qiao_id=qiao_id,
                )
                return None

            user, profile = row
            test_user = {
                "id": user.id,
                "qiao_id": user.qiao_id,
                "nickname": profile.nickname if profile else None,
                "phone": user.phone,
                "status": user.status,
                "user_type": user.user_type,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }

            logger.debug(
                "test_user_retrieved",
                qiao_id=qiao_id,
                nickname=user.nickname,
            )

            return test_user

        except Exception as e:
            logger.error(
                "test_user_retrieval_failed",
                error=str(e),
                qiao_id=qiao_id,
            )
            return None

    async def create_test_user(
        self,
        db: AsyncSession,
        qiao_id: str,
        nickname: str,
        phone: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new test user.

        Args:
            db: Database session
            qiao_id: User's qiao_id
            nickname: User's nickname
            phone: User's phone number (optional)

        Returns:
            Created test user dictionary or None if failed
        """
        try:
            # Check if user already exists
            existing_user = await self.get_test_user_by_qiao_id(db, qiao_id)
            if existing_user:
                logger.warning(
                    "test_user_already_exists",
                    qiao_id=qiao_id,
                )
                return existing_user

            # Create new test user
            new_user = User(
                qiao_id=qiao_id,
                nickname=nickname,
                phone=phone,
                status=1,  # Active
                user_type=3,  # Test user
            )

            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            test_user = {
                "id": new_user.id,
                "qiao_id": new_user.qiao_id,
                "nickname": new_user.nickname,
                "phone": new_user.phone,
                "status": new_user.status,
                "user_type": new_user.user_type,
                "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
            }

            logger.info(
                "test_user_created",
                qiao_id=qiao_id,
                nickname=nickname,
            )

            return test_user

        except Exception as e:
            logger.error(
                "test_user_creation_failed",
                error=str(e),
                qiao_id=qiao_id,
                nickname=nickname,
            )
            await db.rollback()
            return None

    async def update_test_user_status(self, db: AsyncSession, qiao_id: str, status: int) -> bool:
        """
        Update test user status.

        Args:
            db: Database session
            qiao_id: User's qiao_id
            status: New status (1=active, 2=inactive)

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await db.execute(
                select(User).where(and_(User.qiao_id == qiao_id, User.user_type == 3))
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(
                    "test_user_not_found_for_update",
                    qiao_id=qiao_id,
                )
                return False

            user.status = status
            await db.commit()

            logger.info(
                "test_user_status_updated",
                qiao_id=qiao_id,
                new_status=status,
            )

            return True

        except Exception as e:
            logger.error(
                "test_user_status_update_failed",
                error=str(e),
                qiao_id=qiao_id,
                status=status,
            )
            await db.rollback()
            return False

    async def get_test_users_for_selection(self, db: AsyncSession) -> List[Dict[str, str]]:
        """
        Get test users formatted for selection dropdown.

        Args:
            db: Database session

        Returns:
            List of dictionaries with value and label keys
        """
        try:
            test_users = await self.get_test_users(db, active_only=True)

            selection_options = []
            for user in test_users:
                selection_options.append(
                    {
                        "value": user["qiao_id"],
                        "label": f"{user['nickname']} ({user['qiao_id']})",
                    }
                )

            logger.debug(
                "test_users_selection_options_generated",
                count=len(selection_options),
            )

            return selection_options

        except Exception as e:
            logger.error(
                "test_users_selection_options_failed",
                error=str(e),
            )
            return []

    async def validate_test_user(self, db: AsyncSession, qiao_id: str) -> bool:
        """
        Validate that a qiao_id belongs to an active test user.

        Args:
            db: Database session
            qiao_id: User's qiao_id to validate

        Returns:
            True if valid test user, False otherwise
        """
        try:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.qiao_id == qiao_id,
                        User.user_type == 3,
                        User.status == 1,
                    )
                )
            )
            user = result.scalar_one_or_none()

            is_valid = user is not None

            logger.debug(
                "test_user_validation",
                qiao_id=qiao_id,
                is_valid=is_valid,
            )

            return is_valid

        except Exception as e:
            logger.error(
                "test_user_validation_failed",
                error=str(e),
                qiao_id=qiao_id,
            )
            return False


# Default test user service instance
default_test_user_service = TestUserService()
