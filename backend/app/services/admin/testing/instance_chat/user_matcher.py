"""
AI Instance Chat Test User Matcher Service

Provides utilities to list and validate user contacts that can be used for
chat testing with AI instances.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from enums import ContactType, UserType, ProfileOwnerType
from models.contact import Contact
from models.user import User
from models.profile import Profile
from services.ai.types import InstanceContext
from utils.logging import get_logger
from crud.profile import profile as profile_crud
from schemas.profile import ProfileCreate

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

    async def _fetch_virtual_test_users(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Load all virtual (test) users for selection."""
        stmt = (
            select(User, Profile)
            .outerjoin(
                Profile,
                and_(
                    Profile.owner_qiao_id == User.qiao_id,
                    Profile.owner_type == ProfileOwnerType.USER,
                ),
            )
            .where(User.user_type == UserType.VIRTUAL, User.status == 1)
            .order_by(User.created_at.asc())
        )
        rows = await db.execute(stmt)
        virtual_users: List[Dict[str, Any]] = []
        for user, profile in rows.all():
            virtual_users.append(
                {
                    "user_id": user.id,
                    "user_qiao_id": user.qiao_id,
                    "username": user.username,
                    "user_type": user.user_type,
                    "profile": profile.to_dict() if profile else None,
                }
            )
        return virtual_users

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
        contacts = await self._fetch_instance_contacts(db, instance_context["instance_qiao_id"])
        virtual_users = await self._fetch_virtual_test_users(db)

        if not virtual_users:
            raise UserMatcherError(
                "暂无可用 virtual 测试用户",
                error_code="NO_VIRTUAL_USERS",
                suggestions=["在用户管理中创建 user_type=virtual 的账号后重试"],
            )

        contact_user_ids = [contact["user_qiao_id"] for contact in contacts]
        if len(contact_user_ids) > 1:
            raise UserMatcherError(
                "检测到多个测试联系人，请先在联系人管理中清理重复关系",
                error_code="MULTIPLE_VIRTUAL_CONTACTS",
                suggestions=["删除多余的测试联系人后再重试"],
            )

        selection_locked = len(contact_user_ids) == 1
        locked_user_qiao_id = contact_user_ids[0] if selection_locked else None

        if selection_locked:
            selected_entry = next(
                (u for u in virtual_users if u["user_qiao_id"] == locked_user_qiao_id),
                None,
            )
            if not selected_entry:
                raise UserMatcherError(
                    f"锁定的测试用户 {locked_user_qiao_id} 不存在",
                    error_code="LOCKED_TEST_USER_NOT_FOUND",
                    suggestions=["检查 virtual 用户是否被删除或禁用"],
                )
            selected_contact = next(
                (c for c in contacts if c["user_qiao_id"] == locked_user_qiao_id),
                None,
            )
        else:
            selected_entry: Optional[Dict[str, Any]] = None
            if preferred_user_qiao_id:
                selected_entry = next(
                    (u for u in virtual_users if u["user_qiao_id"] == preferred_user_qiao_id),
                    None,
                )
                if not selected_entry:
                    raise UserMatcherError(
                        f"测试用户 {preferred_user_qiao_id} 不存在或不是 virtual",
                        error_code="TEST_USER_NOT_FOUND",
                        suggestions=["重新选择有效的 virtual 用户", "刷新页面同步最新测试用户列表"],
                    )
            elif virtual_users:
                selected_entry = virtual_users[0]

            if not selected_entry:
                raise UserMatcherError(
                    "未找到可用的测试用户",
                    error_code="TEST_USER_SELECTION_FAILED",
                    suggestions=["检查 virtual 用户配置", "刷新页面后重试"],
                )
            selected_contact = None

        contact_map = {contact["user_qiao_id"]: contact for contact in contacts}
        if not selected_contact and selected_entry:
            selected_contact = contact_map.get(selected_entry["user_qiao_id"])
        test_user_info = {
            "id": selected_entry["user_id"],
            "qiao_id": selected_entry["user_qiao_id"],
            "username": selected_entry["username"],
            "user_type": selected_entry["user_type"],
            "conversation_id": (selected_contact or {}).get("conv_id"),
        }
        test_user_profile = await self._ensure_test_user_profile(
            db, test_user_info, existing_profile=selected_entry.get("profile")
        )

        available_test_users = []
        for user_entry in virtual_users:
            profile_dict = user_entry.get("profile")
            contact_info = contact_map.get(user_entry["user_qiao_id"])
            available_test_users.append(
                {
                    "user_qiao_id": user_entry["user_qiao_id"],
                    "username": user_entry["username"],
                    "nickname": (profile_dict or {}).get("nickname"),
                    "has_contact": contact_info is not None,
                    "conv_id": (contact_info or {}).get("conv_id"),
                    "profile": profile_dict,
                }
            )

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
            "test_user_selection_locked": selection_locked,
            "locked_test_user_qiao_id": locked_user_qiao_id,
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
