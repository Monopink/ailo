from typing import Dict, Any, Optional

from core.database import SessionLocal
from ..protocols import ModelAiloLike


class ContactMixin:
    async def _initialize_user_profile(self: ModelAiloLike) -> None:
        """Initialize user profile during model startup

        This method is called asynchronously during model initialization
        to fetch and set up user profile data.
        """
        try:
            if hasattr(self.bot, "user_entity_id") and self.bot.user_entity_id:
                self.user_profile = await self._fetch_user_profile(self.bot.user_entity_id)
                if self.user_profile:
                    self.logger.info("user_profile_initialized", user_entity_id=self.bot.user_entity_id)
                else:
                    self.logger.warning(
                        "failed_to_initialize_user_profile", user_entity_id=self.bot.user_entity_id
                    )
        except Exception as e:
            self.logger.error("error_initializing_user_profile", error=str(e))

    async def _fetch_user_profile(self: ModelAiloLike, user_entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user social profile from contacts service

        Args:
            user_entity_id: User entity ID

        Returns:
            Optional[Dict[str, Any]]: User profile data or None if failed
        """
        try:
            # Use internal service directly (unified architecture)
            from services.contacts.profile import get_social_profile
            from core.database import SessionLocal

            async with SessionLocal() as db:
                current_profile = await get_social_profile(db, user_entity_id)

                if current_profile:
                    self.logger.info("user_profile_fetched", user_entity_id=user_entity_id)

                    # Convert to dict format for compatibility
                    profile_dict = {
                        "entity_id": current_profile.entity_id,
                        "nickname": current_profile.nickname,
                        "bio": current_profile.bio,
                        "gender": current_profile.gender,
                        "birthday": (
                            current_profile.birthday.isoformat() if current_profile.birthday else None
                        ),
                        "interests": current_profile.interests,
                        "preferences": current_profile.preferences,
                    }

                    # Check for profile changes and update snapshot
                    await self._handle_profile_changes(profile_dict)

                    return profile_dict
                else:
                    self.logger.warning("user_profile_not_found", user_entity_id=user_entity_id)
                    return None

        except Exception as e:
            self.logger.error("error_fetching_user_profile", error=str(e), user_entity_id=user_entity_id)
            return None

    async def _handle_profile_changes(self: ModelAiloLike, current_profile: Dict[str, Any]) -> None:
        """Handle user profile changes by comparing with stored snapshot

        Args:
            current_profile: Current user profile data
        """
        try:
            # Get previous snapshot from bot data
            previous_snapshot = getattr(self.bot, "user_profile_snapshot", None)

            if previous_snapshot:
                # Detect changes
                changes = self._detect_profile_changes(previous_snapshot, current_profile)
                if changes:
                    # Add change information to instant context for AI awareness
                    self.profile_changes = f"用户最近更新了个人资料：{changes}"
                    self.logger.info("user_profile_changes_detected", changes=changes)

            # Update snapshot in database
            from crud.bot import bot_crud

            async with SessionLocal() as db:
                await bot_crud.update_bot_data(db, self.bot.id, {"user_profile_snapshot": current_profile})
                self.logger.info("user_profile_snapshot_updated")

        except Exception as e:
            self.logger.error("error_handling_profile_changes", error=str(e))

    def _detect_profile_changes(
        self: ModelAiloLike, old_profile: Dict[str, Any], new_profile: Dict[str, Any]
    ) -> str:
        """Detect changes between old and new user profiles

        Args:
            old_profile: Previous user profile
            new_profile: Current user profile

        Returns:
            str: Description of changes in Chinese
        """
        changes = []

        # Check common fields for changes
        fields = {
            "nickname": "昵称",
            "bio": "个人简介",
            "location": "位置",
            "gender": "性别",
        }

        for field, label in fields.items():
            old_value = old_profile.get(field)
            new_value = new_profile.get(field)

            if old_value != new_value and new_value:
                if old_value:
                    changes.append(f"{label}从「{old_value}」变更为「{new_value}」")
                else:
                    changes.append(f"添加了{label}「{new_value}」")

        return "，".join(changes) if changes else ""

    def _format_user_profile_for_context(self: ModelAiloLike, user_profile: Dict[str, Any]) -> str:
        """Format user profile data for AI context

        Args:
            user_profile: User profile data

        Returns:
            str: Formatted user profile string for context
        """
        user_info = []

        if user_profile.get("nickname"):
            user_info.append(f"昵称：{user_profile['nickname']}")
        if user_profile.get("gender"):
            user_info.append(f"性别：{user_profile['gender']}")
        if user_profile.get("bio"):
            user_info.append(f"简介：{user_profile['bio']}")
        if user_profile.get("location"):
            user_info.append(f"位置：{user_profile['location']}")

        return "，".join(user_info) if user_info else ""
