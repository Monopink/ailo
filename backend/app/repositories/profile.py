from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.social_profile import SocialProfile
from utils.logging import get_logger
from .base import BaseRepository

logger = get_logger(__name__)


class ProfileRepository:
    """Repository for social profile data operations"""

    def __init__(self):
        self.profile_repo = BaseRepository(SocialProfile)

    async def get_social_profile_by_entity_id(
        self, session: AsyncSession, entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get social profile by entity ID

        Args:
            session: Database session
            entity_id: Entity ID

        Returns:
            Social profile dictionary or None if not found
        """
        try:
            result = await session.execute(
                select(SocialProfile).where(SocialProfile.entity_id == entity_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                logger.debug("social_profile_not_found", entity_id=entity_id)
                return None

            return {
                "entity_id": profile.entity_id,
                "nickname": profile.nickname,
                "gender": profile.gender,
                "avatar_url": profile.avatar_url,
                "bio": profile.bio,
                "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
                "location": profile.location,
                "created_at": profile.created_at.isoformat() if profile.created_at else None,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
            }

        except Exception as e:
            logger.error("get_social_profile_by_entity_id_error", error=str(e), entity_id=entity_id)
            raise

    async def create_social_profile(
        self, session: AsyncSession, entity_id: str, profile_data: Dict[str, Any]
    ) -> SocialProfile:
        """
        Create new social profile

        Args:
            session: Database session
            entity_id: Entity ID for the profile
            profile_data: Profile data dictionary

        Returns:
            Created SocialProfile instance
        """
        try:
            new_profile = SocialProfile(
                entity_id=entity_id,
                nickname=profile_data.get("nickname"),
                gender=profile_data.get("gender"),
                avatar_url=profile_data.get("avatar_url"),
                bio=profile_data.get("bio"),
                birth_date=profile_data.get("birth_date"),
                location=profile_data.get("location"),
            )
            session.add(new_profile)
            # Note: Don't commit here, let the calling service handle transaction

            logger.info(
                "social_profile_created", entity_id=entity_id, nickname=profile_data.get("nickname")
            )
            return new_profile

        except Exception as e:
            logger.error("create_social_profile_error", error=str(e), entity_id=entity_id)
            raise

    async def update_social_profile(
        self, session: AsyncSession, entity_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update existing social profile

        Args:
            session: Database session
            entity_id: Entity ID
            updates: Dictionary of fields to update

        Returns:
            Updated social profile dictionary or None if not found
        """
        try:
            result = await session.execute(
                select(SocialProfile).where(SocialProfile.entity_id == entity_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                logger.warning("social_profile_not_found_for_update", entity_id=entity_id)
                return None

            # Apply updates
            for field, value in updates.items():
                if hasattr(profile, field):
                    setattr(profile, field, value)

            # Note: Don't commit here, let the calling service handle transaction

            logger.info("social_profile_updated", entity_id=entity_id, updated_fields=list(updates.keys()))

            # Return updated profile data
            return {
                "entity_id": profile.entity_id,
                "nickname": profile.nickname,
                "gender": profile.gender,
                "avatar_url": profile.avatar_url,
                "bio": profile.bio,
                "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
                "location": profile.location,
                "created_at": profile.created_at.isoformat() if profile.created_at else None,
                "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
            }

        except Exception as e:
            logger.error("update_social_profile_error", error=str(e), entity_id=entity_id)
            raise

    async def create_or_update_social_profile(
        self, session: AsyncSession, entity_id: str, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update social profile (upsert operation)

        Args:
            session: Database session
            entity_id: Entity ID
            profile_data: Profile data dictionary

        Returns:
            Profile dictionary
        """
        try:
            # Check if profile exists
            existing_profile = await self.get_social_profile_by_entity_id(session, entity_id)

            if existing_profile:
                # Update existing profile
                updated_profile = await self.update_social_profile(session, entity_id, profile_data)
                if updated_profile is None:
                    raise ValueError(f"Failed to update profile for entity_id: {entity_id}")
                return updated_profile
            else:
                # Create new profile
                new_profile = await self.create_social_profile(session, entity_id, profile_data)
                return {
                    "entity_id": new_profile.entity_id,
                    "nickname": new_profile.nickname,
                    "gender": new_profile.gender,
                    "avatar_url": new_profile.avatar_url,
                    "bio": new_profile.bio,
                    "birth_date": new_profile.birth_date.isoformat() if new_profile.birth_date else None,
                    "location": new_profile.location,
                    "created_at": new_profile.created_at.isoformat() if new_profile.created_at else None,
                    "updated_at": new_profile.updated_at.isoformat() if new_profile.updated_at else None,
                }

        except Exception as e:
            logger.error("create_or_update_social_profile_error", error=str(e), entity_id=entity_id)
            raise
