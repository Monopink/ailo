"""
AI character and context related models.

This module contains SQLAlchemy models for AI characters and conversation contexts.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, String, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import SnowflakeModel, SnowflakeQiaoModel

if TYPE_CHECKING:
    from models.user import User
    from models.ai.style import AIStyle
    from models.ai.personality import AIPersonality


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

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive, 3=blocked",
    )

    memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Character memory settings")

    prompt_variables: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Prompt variables/placeholder overrides (JSONB for better performance)",
    )

    score_offset_algorithm: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        server_default=text("1"),
        comment="Score offset algorithm (enum int)",
    )

    score_offset_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text('\'{"left_bias": 0, "right_bias": 0}\''),
        comment="Score offset parameters (JSONB for better performance)",
    )

    request_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI character request parameters configuration (can override default LLM settings)",
    )

    created_by: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Creator type: 1=system, 2=user"
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="AICharacter.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )
    style: Mapped["AIStyle"] = relationship(
        "AIStyle",
        primaryjoin="AICharacter.style_id == AIStyle.id",
        foreign_keys=[style_id],
        lazy="select",
        viewonly=True,
    )
    personality: Mapped["AIPersonality"] = relationship(
        "AIPersonality",
        primaryjoin="AICharacter.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes - Only essential indexes for MVP
    # Note: qiao_id already has unique index
    __table_args__ = (
        Index("idx_ai_characters_user_qiao_id", "user_qiao_id"),
        Index("idx_ai_characters_style_id", "style_id"),
        Index("idx_ai_characters_personality_id", "personality_id"),
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

    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Token count")

    is_attack: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is attack message: 1=yes, 0=no",
    )

    reply_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Reply status: 1=pending, 2=processing, 3=done",
    )

    # Indexes - Only essential indexes for MVP
    __table_args__ = (
        Index("idx_ai_contexts_character_qiao_id", "character_qiao_id"),
        Index("idx_ai_contexts_user_qiao_id", "user_qiao_id"),
        Index("idx_ai_contexts_created_at", "created_at"),
        Index("idx_ai_contexts_reply_status", "reply_status"),
        Index("idx_ai_contexts_character_id", "character_id"),
    )


class AIContextArchive(SnowflakeModel):
    """
    AI context archive model.

    Archived AI conversation context and history.
    """

    __tablename__ = "ai_contexts_archive"

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
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Source type: 1=original, 2=merged, 3=summarized",
    )

    source_message_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSONB, nullable=True, comment="Source message ID list (JSONB for better performance)"
    )

    context_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Context metadata (JSONB for better performance)"
    )

    token_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Token count for this context"
    )

    is_attack: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is attack message: 1=yes, 0=no",
    )

    reply_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Reply status: 1=pending, 2=processing, 3=done",
    )
