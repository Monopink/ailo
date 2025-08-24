"""
AI character and context related models.

This module contains SQLAlchemy models for AI characters and conversation contexts.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import Index as PGIndex
from sqlalchemy.orm import Mapped, mapped_column

from enums import AICharacterCreator, AIContextRole, AIContextSourceType
from models.base import SnowflakeModel, SnowflakeQiaoModel


class AICharacter(SnowflakeQiaoModel):
    """
    AI character model.

    AI character instances created by users or system.
    """

    __tablename__ = "ai_characters"

    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Owner user ID, references users.id"
    )

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Owner user external ID"
    )

    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Character category")

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Character memory settings")

    placeholder_overrides: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Placeholder overrides (JSONB for better performance)"
    )

    score_offset_algorithm: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Score offset algorithm"
    )

    score_offset_coefficient: Mapped[Optional[float]] = mapped_column(
        nullable=True, comment="Score offset coefficient"
    )

    created_by: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Creator type: 1=system, 2=user"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ai_characters_user_id", "user_id"),
        Index("idx_ai_characters_user_qiao_id", "user_qiao_id"),
        Index("idx_ai_characters_category", "category"),
        Index("idx_ai_characters_style_id", "style_id"),
        Index("idx_ai_characters_personality_id", "personality_id"),
        Index("idx_ai_characters_created_by", "created_by"),
        # PostgreSQL GIN index for JSONB field for better query performance
        PGIndex(
            "idx_ai_characters_placeholder_overrides_gin", "placeholder_overrides", postgresql_using="gin"
        ),
    )


class AIContext(SnowflakeModel):
    """
    AI context model.

    AI conversation context and history.
    """

    __tablename__ = "ai_contexts"

    character_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Character ID, references ai_characters.id"
    )

    character_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Character external ID"
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="User ID, references users.id")

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="User external ID")

    role: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Role type: 1=system, 2=user, 3=assistant"
    )

    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Message content")

    source_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Source type: 1=original, 2=summary, 3=generated"
    )

    source_message_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSONB, nullable=True, comment="Source message ID list (JSONB for better performance)"
    )

    context_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Context metadata (JSONB for better performance)"
    )

    position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Position in conversation sequence"
    )

    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Token count")

    # Indexes
    __table_args__ = (
        Index("idx_ai_contexts_character_id", "character_id"),
        Index("idx_ai_contexts_character_qiao_id", "character_qiao_id"),
        Index("idx_ai_contexts_user_id", "user_id"),
        Index("idx_ai_contexts_user_qiao_id", "user_qiao_id"),
        Index("idx_ai_contexts_role", "role"),
        Index("idx_ai_contexts_position", "position"),
        # PostgreSQL GIN indexes for JSONB fields for better query performance
        PGIndex("idx_ai_contexts_source_message_ids_gin", "source_message_ids", postgresql_using="gin"),
        PGIndex("idx_ai_contexts_context_metadata_gin", "context_metadata", postgresql_using="gin"),
    )
