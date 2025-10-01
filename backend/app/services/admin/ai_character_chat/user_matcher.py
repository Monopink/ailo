"""
AI Character Chat Test User Matcher Service

Automatically finds and validates test users associated with AI characters,
ensuring proper relationship establishment for testing purposes.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
from models.contact import Contact
from models.profile import Profile
from utils.logging import get_logger

logger = get_logger(__name__)


class UserMatcherError(Exception):
    """Exception raised when test user matching fails"""

    def __init__(
        self, message: str, error_code: str = "USER_MATCHER_ERROR", suggestions: Optional[list] = None
    ):
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []
        super().__init__(message)


class UserMatcherService:
    """Stateless service for automatic test user matching and validation"""

    async def find_test_user_for_character(
        self, db: AsyncSession, character_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Find and validate test user associated with the given AI character.

        Args:
            db: Database session
            character_info: AI character information from validation

        Returns:
            Dictionary containing test user information and relationship data

        Raises:
            UserMatcherError: If test user not found or invalid
        """
        try:
            # Find contact relationship where user is test user (user_type=3) and contact is this AI character
            test_user_info = await self._find_associated_test_user(db, character_info)

            # Validate test user profile exists
            test_user_profile = await self._validate_test_user_profile(db, test_user_info)

            logger.info(
                "test_user_match_success",
                character_qiao_id=character_info["qiao_id"],
                test_user_qiao_id=test_user_info["qiao_id"],
                conversation_id=test_user_info["conversation_id"],
            )

            return {
                "test_user": test_user_info,
                "test_user_profile": test_user_profile,
            }

        except UserMatcherError:
            raise
        except Exception as e:
            logger.error(
                "test_user_match_error", character_qiao_id=character_info.get("qiao_id"), error=str(e)
            )
            raise UserMatcherError(
                f"Test user matching failed due to system error: {str(e)}", error_code="SYSTEM_ERROR"
            )

    async def _find_associated_test_user(
        self, db: AsyncSession, character_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find test user associated with this AI character"""
        stmt = (
            select(Contact, User)
            .where(
                Contact.contact_qiao_id == character_info["qiao_id"],
                Contact.contact_type == 2,  # AI character
            )
            .join(User, Contact.user_id == User.id)
            .where(User.user_type == 3)  # Test user
        )

        result = await db.execute(stmt)
        row = result.one_or_none()

        if not row:
            raise UserMatcherError(
                f"No test user associated with AI character '{character_info['qiao_id']}'",
                error_code="TEST_USER_NOT_FOUND",
                suggestions=[
                    "Create a test user and establish contact relationship",
                    "Check Contacts management to link test user with AI character",
                    "Verify test user has user_type=3",
                ],
            )

        contact, test_user = row
        if test_user.status != 1:  # ACTIVE
            raise UserMatcherError(
                f"Test user '{test_user.qiao_id}' is not active",
                error_code="TEST_USER_INACTIVE",
                suggestions=["Activate the test user", "Check user status in Users management"],
            )

        return {
            "id": test_user.id,
            "qiao_id": test_user.qiao_id,
            "username": test_user.username,
            "user_type": test_user.user_type,
            "contact_id": contact.id,
            "conversation_id": contact.conv_id,
        }

    async def _validate_test_user_profile(
        self, db: AsyncSession, test_user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate test user profile exists"""
        stmt = select(Profile).where(
            Profile.owner_qiao_id == test_user_info["qiao_id"], Profile.owner_type == 1  # User
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            raise UserMatcherError(
                f"Profile not found for test user '{test_user_info['qiao_id']}'",
                error_code="TEST_USER_PROFILE_MISSING",
                suggestions=[
                    "Create a profile for the test user",
                    "Check Profile management for test users",
                ],
            )

        return {
            "nickname": profile.nickname,
            "bio": profile.bio,
            "gender": profile.gender,
            "avatar_url": profile.avatar_url,
        }

    async def get_all_test_users(self, db: AsyncSession) -> list[Dict[str, Any]]:
        """
        Get all available test users for administrative purposes.

        Args:
            db: Database session

        Returns:
            List of test user information dictionaries
        """
        try:
            # Query users and their profiles separately
            stmt = select(User).where(User.user_type == 3, User.status == 1).order_by(User.username)

            result = await db.execute(stmt)
            test_users = result.scalars().all()

            # Get profiles for these users
            user_qiao_ids = [user.qiao_id for user in test_users]
            profile_stmt = select(Profile).where(
                Profile.owner_qiao_id.in_(user_qiao_ids), Profile.owner_type == 1
            )
            profile_result = await db.execute(profile_stmt)
            profiles = {p.owner_qiao_id: p for p in profile_result.scalars().all()}

            return [
                {
                    "id": user.id,
                    "qiao_id": user.qiao_id,
                    "username": user.username,
                    "has_profile": user.qiao_id in profiles,
                    "profile_nickname": (
                        profiles[user.qiao_id].nickname if user.qiao_id in profiles else None
                    ),
                }
                for user in test_users
            ]

        except Exception as e:
            logger.error("get_all_test_users_error", error=str(e))
            raise UserMatcherError(f"Failed to retrieve test users: {str(e)}", error_code="RETRIEVE_ERROR")


# Global instance for dependency injection
user_matcher_service = UserMatcherService()
