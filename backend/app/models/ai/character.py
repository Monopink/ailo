"""
AI character and context related models.

This module contains SQLAlchemy models for AI characters and conversation contexts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import SnowflakeModel, SnowflakeQiaoModel, ImmutableSnowflakeModel

if TYPE_CHECKING:
    from models.user import User
    from models.ai.style import AIStyle, AIRelationship
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

    request_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI character request parameters configuration (can override default LLM settings)",
    )

    created_from_profile_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Source profile template qiao_id (if created from template)"
    )

    relationship_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Current relationship type ID"
    )

    relationship_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Relationship usage counts (JSONB)",
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
    dimensions: Mapped[List["AICharacterDimension"]] = relationship(
        "AICharacterDimension",
        primaryjoin="AICharacter.id == foreign(AICharacterDimension.character_id)",
        lazy="select",
        viewonly=True,
    )
    relationship: Mapped[Optional["AIRelationship"]] = relationship(
        "AIRelationship",
        primaryjoin="AICharacter.relationship_id == AIRelationship.id",
        foreign_keys=[relationship_id],
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


class AIMessageBuffer(SnowflakeModel):
    """
    Message aggregation window metadata for incoming user messages.
    """

    __tablename__ = "ai_message_buffer"

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="User external ID")
    character_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Character external ID")
    aggregate_state: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Buffer state: 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED"
    )
    micro_expires_at_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Micro timer expiration timestamp (ms)"
    )
    macro_expires_at_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Macro timer expiration timestamp (ms)"
    )
    buffer_expires_at_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Next timer deadline (min of micro/macro)"
    )
    last_message_category: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Last inbound message category"
    )
    first_msg_id_client: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="First client message ID within buffer"
    )
    last_msg_id_client: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Last client message ID within buffer"
    )
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"), comment="Number of messages in buffer"
    )
    last_msg_time_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Timestamp (ms) of last message appended to buffer"
    )
    locked_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Timestamp when buffer entered LOCKED state"
    )

    __table_args__ = (
        Index("idx_ai_message_buffer_session_state", "user_qiao_id", "character_qiao_id", "aggregate_state"),
        Index(
            "idx_ai_message_buffer_micro",
            "micro_expires_at_ms",
            postgresql_where=text("aggregate_state = 1 AND micro_expires_at_ms IS NOT NULL"),
        ),
        Index(
            "idx_ai_message_buffer_macro",
            "macro_expires_at_ms",
            postgresql_where=text("aggregate_state = 1 AND macro_expires_at_ms IS NOT NULL"),
        ),
        Index(
            "idx_ai_message_buffer_locked",
            "user_qiao_id",
            "character_qiao_id",
            unique=True,
            postgresql_where=text("aggregate_state = 2"),
        ),
        Index(
            "idx_ai_message_buffer_expire_scan",
            "user_qiao_id",
            "character_qiao_id",
            "buffer_expires_at_ms",
            postgresql_where=text("aggregate_state = 1 AND buffer_expires_at_ms IS NOT NULL"),
        ),
    )


class AIConversationItem(ImmutableSnowflakeModel):
    """Conversation item stored as Responses API content blocks (immutable)."""

    __tablename__ = "ai_conversation_items"

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="User external ID")
    character_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Character external ID")
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="Message role: system/user/assistant")
    content: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Responses API content blocks array",
    )
    content_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Preview for admin tooling")
    client_msg_ids: Mapped[List[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
        comment="Client message IDs merged into this row",
    )
    buffer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated buffer ID (references ai_message_buffer.id, no FK constraint)",
    )
    llm_config_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="LLM configuration ID (references llm_configs.id, no FK constraint)",
    )
    response_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Provider response identifier for assistant rows"
    )
    is_excluded_from_context: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Flag to exclude this row from LLM context (prompt injection, etc.)",
    )

    __table_args__ = (
        Index("idx_ai_conv_items_session", "user_qiao_id", "character_qiao_id", "created_at"),
        Index(
            "idx_ai_conv_items_buffer",
            "buffer_id",
            postgresql_where=text("buffer_id IS NOT NULL"),
        ),
        Index(
            "idx_ai_conv_items_response",
            "response_id",
            postgresql_where=text("response_id IS NOT NULL"),
        ),
        Index(
            "idx_ai_conv_items_excluded",
            "user_qiao_id",
            "character_qiao_id",
            "created_at",
            postgresql_where=text("is_excluded_from_context = true"),
        ),
        CheckConstraint(
            "(role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user' AND buffer_id IS NULL)",
            name="ck_ai_conversation_items_user_buffer",
        ),
    )


class AIConversationItemArchive(ImmutableSnowflakeModel):
    """Archived conversation rows for cold storage (immutable)."""

    __tablename__ = "ai_conversation_items_archive"

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="User external ID")
    character_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Character external ID")
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="Message role: system/user/assistant")
    content: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Responses API content blocks array",
    )
    content_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Preview for admin tooling")
    client_msg_ids: Mapped[List[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
        comment="Client message IDs merged into this row",
    )
    buffer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated buffer ID (references ai_message_buffer.id, no FK constraint)",
    )
    llm_config_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="LLM configuration ID (references llm_configs.id, no FK constraint)",
    )
    response_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Provider response identifier for assistant rows"
    )
    is_excluded_from_context: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Flag to exclude this row from LLM context (prompt injection, etc.)",
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Archive timestamp"
    )

    __table_args__ = (
        Index("idx_ai_conv_items_archive_session", "user_qiao_id", "character_qiao_id", "created_at"),
    )
