"""
AI Instance Chat Test User Matcher Service

Provides utilities to list and validate user contacts that can be used for
chat testing with AI instances.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from enums import ContactType, ProfileOwnerType, UserType
from models.contact import Contact
from models.user import User
from models.profile import Profile
from utils.logging import get_logger
from crud.profile import profile as profile_crud
from schemas.profile import ProfileCreate
from services.ai.types import InstanceContext

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
    """Stateless service for selecting and validating instance contacts"""

    async def _fetch_instance_owner(
        self, db: AsyncSession, instance_context: InstanceContext
    ) -> Dict[str, Any]:
        """Load the owning user for this instance."""
        stmt = (
            select(User, Profile)
            .outerjoin(
                Profile,
                and_(
                    Profile.owner_qiao_id == User.qiao_id,
                    Profile.owner_type == ProfileOwnerType.USER,
                ),
            )
            .where(User.id == instance_context["user_id"])
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            raise UserMatcherError(
                "未找到该实例的归属用户",
                error_code="OWNER_NOT_FOUND",
                suggestions=[
                    "检查实例是否绑定了用户",
                    "确认用户账号未被删除",
                ],
            )

        user, profile = row

        return {
            "user_id": user.id,
            "user_qiao_id": user.qiao_id,
            "username": user.username,
            "user_type": user.user_type,
            "profile": profile.to_dict() if profile else None,
        }

    async def find_test_user_for_instance(
        self,
        db: AsyncSession,
        instance_context: InstanceContext,
        preferred_user_qiao_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find and validate test user associated with the given AI instance.

        Args:
            db: Database session
            instance_context: AI instance context from validation
            preferred_user_qiao_id: Optional user qiao_id selected by admin

        Returns:
            Dict containing selected test user info (if resolved) and available contacts.
        """
        owner = await self._fetch_instance_owner(db, instance_context)
        if owner["user_type"] != UserType.VIRTUAL:
            raise UserMatcherError(
                "实例归属用户不是测试账号，无法执行测试",
                error_code="OWNER_NOT_VIRTUAL",
                suggestions=["请对测试用户的实例进行测试"],
            )

        contacts = await self._fetch_instance_contacts(db, instance_context["instance_qiao_id"])
        selected_contact = next((c for c in contacts if c["user_qiao_id"] == owner["user_qiao_id"]), None)

        test_user_info = {
            "id": owner["user_id"],
            "qiao_id": owner["user_qiao_id"],
            "username": owner["username"],
            "user_type": owner["user_type"],
            "conversation_id": selected_contact["conv_id"] if selected_contact else None,
        }
        test_user_profile = await self._ensure_test_user_profile(
            db, test_user_info, existing_profile=owner.get("profile")
        )

        available_test_users = [
            {
                "user_qiao_id": owner["user_qiao_id"],
                "username": owner["username"],
                "nickname": (test_user_profile or {}).get("nickname"),
                "has_contact": selected_contact is not None,
                "conv_id": selected_contact["conv_id"] if selected_contact else None,
                "profile": test_user_profile,
            }
        ]

        logger.info(
            "test_user_match_success",
            instance_qiao_id=instance_context["instance_qiao_id"],
            test_user_qiao_id=test_user_info["qiao_id"],
            conversation_id=test_user_info.get("conversation_id"),
        )

        return {
            "test_user": test_user_info,
            "test_user_profile": test_user_profile,
            "contact": selected_contact,
            "available_contacts": contacts,
            "available_test_users": available_test_users,
            "recomputed_contacts": contacts,
            "test_user_selection_locked": True,
            "locked_test_user_qiao_id": owner["user_qiao_id"],
        }

    async def _ensure_test_user_profile(
        self,
        db: AsyncSession,
        test_user_info: Dict[str, Any],
        existing_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure test user profile exists; auto-create empty profile when missing.
        """
        if existing_profile:
            return existing_profile

        stmt = select(Profile).where(
            Profile.owner_qiao_id == test_user_info["qiao_id"],
            Profile.owner_type == ProfileOwnerType.USER,
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile:
            return profile.to_dict()

        created = await profile_crud.create_with_owner(
            db,
            obj_in=ProfileCreate(),
            owner_id=test_user_info["id"],
            owner_qiao_id=test_user_info["qiao_id"],
            owner_type=ProfileOwnerType.USER,
            commit=False,
        )
        await db.flush()
        logger.info(
            "virtual_test_user_profile_auto_created",
            test_user_qiao_id=test_user_info["qiao_id"],
        )
        return created.to_dict()

    async def _fetch_instance_contacts(
        self, db: AsyncSession, instance_qiao_id: str
    ) -> List[Dict[str, Any]]:
        """
        Load all active user contacts linked to this AI instance.
        """
        stmt = (
            select(Contact, User, Profile)
            .join(User, Contact.user_id == User.id)
            .outerjoin(
                Profile,
                and_(
                    Profile.owner_qiao_id == User.qiao_id,
                    Profile.owner_type == ProfileOwnerType.USER,
                ),
            )
            .where(
                Contact.contact_qiao_id == instance_qiao_id,
                Contact.contact_type == ContactType.AI,
                Contact.is_deleted == 0,
                User.user_type == UserType.VIRTUAL,
            )
            .order_by(Contact.created_at.asc())
        )

        rows = await db.execute(stmt)
        contacts: List[Dict[str, Any]] = []
        for contact, user, profile in rows.all():
            contacts.append(
                {
                    "contact_id": contact.id,
                    "conv_id": contact.conv_id,
                    "user_id": user.id,
                    "user_qiao_id": user.qiao_id,
                    "username": user.username,
                    "user_type": user.user_type,
                    "nickname": profile.nickname if profile else None,
                    "gender": profile.gender if profile else None,
                    "region": profile.region if profile else None,
                    "bio": profile.bio if profile else None,
                    "avatar_url": profile.avatar_url if profile else None,
                    "avatar_prompt": profile.avatar_prompt if profile else None,
                }
            )

        return contacts


user_matcher_service = UserMatcherService()

__all__ = ["UserMatcherService", "UserMatcherError", "user_matcher_service"]
