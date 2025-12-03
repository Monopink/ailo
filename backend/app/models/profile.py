"""
Profile management related models.

This module contains SQLAlchemy models for user profiles and profile change logs.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ProfileOwnerType
from app.models.base import ImmutableSnowflakeModel, SnowflakeModel

if TYPE_CHECKING:
    from app.models.ai.instance import AIInstance
    from app.models.ai.template import AIPersona
    from app.models.user import User


class Profile(SnowflakeModel):
    """
    Profile model.

    Unified profile data for users, AI instances, and official accounts.
    """

    __tablename__ = "profiles"

    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Owner internal ID")

    owner_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Owner external ID (globally unique)"
    )

    owner_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Owner type: 1=user (all user types), 2=ai"
    )

    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Display nickname"
    )

    gender: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )

    avatar_file_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Avatar file ID, references media_files.id"
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Avatar URL (redundant for query optimization)"
    )

    avatar_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Avatar description for AI-generated avatars"
    )

    bio: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Personal bio/description")

    region: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Location/region"
    )

    # Polymorphic owner relationships
    # owner_type=1 (USER) → users table (includes all user types: normal, official, virtual)
    _owner_user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="and_(Profile.owner_id == User.id, Profile.owner_type == 1)",
        foreign_keys=[owner_id],
        lazy="select",
        viewonly=True,
    )

    # owner_type=2 (AI_PERSONA) → ai_personas table
    _owner_persona: Mapped[Optional["AIPersona"]] = relationship(
        "AIPersona",
        primaryjoin="and_(Profile.owner_id == AIPersona.id, Profile.owner_type == 2)",
        foreign_keys=[owner_id],
        lazy="select",
        viewonly=True,
    )

    # owner_type=3 (AI_INSTANCE) → ai_instances table
    _owner_instance: Mapped[Optional["AIInstance"]] = relationship(
        "AIInstance",
        primaryjoin="and_(Profile.owner_id == AIInstance.id, Profile.owner_type == 3)",
        foreign_keys=[owner_id],
        lazy="select",
        viewonly=True,
    )

    @hybrid_property
    def owner(self):
        """Return the appropriate owner object based on owner_type."""
        if self.owner_type == ProfileOwnerType.USER:
            return self._owner_user
        if self.owner_type == ProfileOwnerType.AI_PERSONA:
            return self._owner_persona
        if self.owner_type == ProfileOwnerType.AI_INSTANCE:
            return self._owner_instance
        return None


class UserProfileLog(ImmutableSnowflakeModel):
    """
    User profile log model.

    Tracks profile changes for users only.
    Immutable log - profile changes should not be modified after creation.
    """

    __tablename__ = "user_profile_logs"

    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Owner internal ID")

    owner_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Owner external ID"
    )

    owner_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Owner type: 1=user, 2=ai, 3=official"
    )

    modified_by_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Modifier type: 1=user, 2=admin, 3=system"
    )

    field_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Modified field name"
    )

    old_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Old value")

    new_value: Mapped[str | None] = mapped_column(Text, nullable=True, comment="New value")

    change_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Change reason"
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_profile_logs_owner_id", "owner_id"),
        Index("idx_user_profile_logs_owner_qiao_id", "owner_qiao_id"),
        Index("idx_user_profile_logs_field_name", "field_name"),
        Index("idx_user_profile_logs_modified_by_type", "modified_by_type"),
        Index("idx_user_profile_logs_created_at", "created_at"),
    )
