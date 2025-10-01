"""
Profile management related models.

This module contains SQLAlchemy models for user profiles and profile change logs.
"""

from typing import Optional
from sqlalchemy import BigInteger, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from enums import Gender, ProfileOwnerType, ProfileModifierType
from models.base import SnowflakeModel, ImmutableSnowflakeModel


class Profile(SnowflakeModel):
    """
    Profile model.

    Unified profile data for users, AI characters, and official accounts.
    """

    __tablename__ = "profiles"

    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Owner internal ID")

    owner_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Owner external ID")

    owner_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Owner type: 1=user, 2=ai, 3=official"
    )

    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Display nickname")

    gender: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Gender: 1=male, 2=female, 3=other, 4=unknown"
    )

    avatar_file_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Avatar file ID, references media_files.file_id"
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Avatar URL (redundant for query optimization)"
    )

    avatar_prompt: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Avatar description for AI-generated avatars"
    )

    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Personal bio/description")

    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Location/region")

    # Indexes
    __table_args__ = (
        Index("idx_profiles_owner_qiao_id", "owner_qiao_id"),
        Index("idx_profiles_owner_id", "owner_id"),
        Index("idx_profiles_owner_type", "owner_type"),
        Index("idx_profiles_nickname", "nickname"),
        Index("idx_profiles_gender", "gender"),
        Index("idx_profiles_region", "region"),
    )


class UserProfileLog(ImmutableSnowflakeModel):
    """
    User profile log model.

    Tracks profile changes for users only.
    Immutable log - profile changes should not be modified after creation.
    """

    __tablename__ = "user_profile_logs"

    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Owner internal ID")

    owner_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Owner external ID")

    owner_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Owner type: 1=user, 2=ai, 3=official"
    )

    modified_by_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Modifier type: 1=user, 2=admin, 3=system"
    )

    field_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="Modified field name")

    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Old value")

    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="New value")

    change_reason: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="Change reason"
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_profile_logs_owner_id", "owner_id"),
        Index("idx_user_profile_logs_owner_qiao_id", "owner_qiao_id"),
        Index("idx_user_profile_logs_field_name", "field_name"),
        Index("idx_user_profile_logs_modified_by_type", "modified_by_type"),
        Index("idx_user_profile_logs_created_at", "created_at"),
    )
