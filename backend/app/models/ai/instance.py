"""AI instance and context related models.

This module contains SQLAlchemy models for AI instances and conversation contexts.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from markupsafe import escape
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship
from starlette.requests import Request

from app.enums.common import ConversationItemContextStatus
from app.models.base import (
    Base,
    ImmutableSnowflakeModel,
    SnowflakeModel,
    SnowflakeQiaoModel,
    TimestampMixin,
    generate_qiao_id,
)
from app.type_defs import JSONDict

if TYPE_CHECKING:
    from app.models.ai.instance_dimension import AIInstanceDimension
    from app.models.ai.personality import AIPersonality
    from app.models.ai.style import AIRelationship, AIStyle
    from app.models.user import User


class AIInstance(SnowflakeQiaoModel):
    """AI instance model.

    Represents a user-specific instantiation of a persona/template.
    """

    __tablename__ = "ai_instances"

    qiao_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=generate_qiao_id,
        comment="External persona identifier (multiple users can add same persona)",
    )
    username: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment=(
            "Runtime username snapshot; source=persona must equal persona.username, "
            "source=admin_manual must be NULL"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Owning user ID, references users.id"
    )

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Owning user qiao_id"
    )

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    creation_metadata: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Snapshot of instance creation data for auditing",
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive, 3=blocked",
    )

    prompt_variables: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Prompt variables/placeholder overrides (JSONB for better performance)",
    )

    request_params: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI instance request parameter overrides (LLM settings)",
    )
    llm_config_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="LLM config ID for this instance (no FK constraint)",
    )

    typing_speed_wpm: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Typing speed (words per minute) used for message delays",
    )

    relationship_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Current relationship type ID"
    )

    relationship_counts: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'::jsonb"),
        comment="Relationship usage counts (JSONB)",
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Shanghai",
        server_default=text("'Asia/Shanghai'"),
        comment="IANA timezone for time formatting",
    )

    created_by: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Creator type: 1=system, 2=user"
    )

    # Relationships
    user: Mapped["User"] = orm_relationship(
        "User",
        primaryjoin="AIInstance.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )
    style: Mapped["AIStyle"] = orm_relationship(
        "AIStyle",
        primaryjoin="AIInstance.style_id == AIStyle.id",
        foreign_keys=[style_id],
        lazy="select",
        viewonly=True,
    )
    personality: Mapped["AIPersonality"] = orm_relationship(
        "AIPersonality",
        primaryjoin="AIInstance.personality_id == AIPersonality.id",
        foreign_keys=[personality_id],
        lazy="select",
        viewonly=True,
    )
    instance_dimensions: Mapped[list["AIInstanceDimension"]] = orm_relationship(
        "AIInstanceDimension",
        primaryjoin="AIInstance.id == foreign(AIInstanceDimension.instance_id)",
        lazy="select",
        viewonly=True,
    )
    relationship: Mapped["AIRelationship | None"] = orm_relationship(
        "AIRelationship",
        primaryjoin="AIInstance.relationship_id == AIRelationship.id",
        foreign_keys=[relationship_id],
        lazy="select",
        viewonly=True,
    )
    llm_config = orm_relationship(
        "LLMConfig",
        lazy="select",
        viewonly=True,
        uselist=False,
        primaryjoin="AIInstance.llm_config_id == foreign(LLMConfig.id)",
    )

    # Indexes - Only essential indexes for MVP
    # Note: qiao_id is indexed for lookup
    __table_args__ = (
        UniqueConstraint("user_id", "qiao_id", name="uq_ai_instances_user_qiao"),
        CheckConstraint(
            "(creation_metadata->>'source') <> 'admin_manual' OR username IS NULL",
            name="ck_ai_instances_manual_username_null",
        ),
        Index("idx_ai_instances_user_id", "user_id"),
        Index("idx_ai_instances_user_qiao_id", "user_qiao_id"),
        Index("idx_ai_instances_user_username", "user_id", "username"),
        Index("idx_ai_instances_style_id", "style_id"),
        Index("idx_ai_instances_personality_id", "personality_id"),
    )

    def __admin_select2_repr__(self, request: Request) -> str:
        return f"<span>[{self.id}] {escape(self.qiao_id)} / {escape(self.user_qiao_id)}</span>"


class AIMessageBuffer(SnowflakeModel):
    """Message aggregation window metadata for incoming user messages."""

    __tablename__ = "ai_message_buffer"

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )
    instance_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Instance external ID"
    )
    aggregate_state: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Buffer state: 0=WAITING_WAKEUP, 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED",
    )
    micro_expires_at_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Micro timer expiration timestamp (ms)"
    )
    macro_expires_at_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Macro timer expiration timestamp (ms)"
    )
    buffer_expires_at_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Effective processing deadline (ms), combining micro/macro timers with wake gate",
    )
    last_message_category: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Last inbound message category"
    )
    first_msg_id_client: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="First client message ID within buffer"
    )
    last_msg_id_client: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Last client message ID within buffer"
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Number of messages in buffer",
    )
    last_msg_time_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Timestamp (ms) of last message appended to buffer"
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Timestamp when buffer entered LOCKED state"
    )
    wake_expires_at_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Wake gate deadline (ms), NULL when wake gate is inactive",
    )
    wake_adjustment_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of times wake time was adjusted by new messages",
    )

    __table_args__ = (
        Index(
            "idx_ai_message_buffer_session_state",
            "user_qiao_id",
            "instance_qiao_id",
            "aggregate_state",
        ),
        Index(
            "idx_ai_message_buffer_locked",
            "user_qiao_id",
            "instance_qiao_id",
            unique=True,
            postgresql_where=text("aggregate_state = 2"),
        ),
        Index(
            "idx_ai_message_buffer_expire_scan",
            "user_qiao_id",
            "instance_qiao_id",
            "buffer_expires_at_ms",
            postgresql_where=text("aggregate_state IN (0, 1) AND buffer_expires_at_ms IS NOT NULL"),
        ),
    )


class AIConversationItem(ImmutableSnowflakeModel):
    """Conversation item stored as simple typed fields (immutable)."""

    __tablename__ = "ai_conversation_items"

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )
    instance_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Instance external ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Message role: system/user/assistant"
    )
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default=text("'text'"),
        comment="Message type: text/image/audio",
    )
    text_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text content (for message_type=text)",
    )
    media_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Media URL for image/audio messages",
    )
    media_metadata: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Media metadata (dimensions, transcript, duration, etc.)",
    )
    client_msg_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
        comment="Client message IDs merged into this row",
    )
    buffer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated buffer ID (references ai_message_buffer.id, no FK constraint)",
    )
    is_excluded_from_context: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Context inclusion status: 0=included, 1=excluded (prompt injection, etc.)",
    )

    __table_args__ = (
        Index("idx_ai_conv_items_session", "user_qiao_id", "instance_qiao_id", "created_at"),
        Index(
            "idx_ai_conv_items_buffer",
            "buffer_id",
            postgresql_where=text("buffer_id IS NOT NULL"),
        ),
        Index(
            "idx_ai_conv_items_excluded",
            "user_qiao_id",
            "instance_qiao_id",
            "created_at",
            postgresql_where=text(
                f"is_excluded_from_context = {int(ConversationItemContextStatus.EXCLUDED)}"
            ),
        ),
        Index(
            "idx_ai_conv_items_text_search",
            "text_content",
            postgresql_using="gin",
            postgresql_ops={"text_content": "gin_trgm_ops"},
        ),
        CheckConstraint(
            "(message_type = 'text' AND text_content IS NOT NULL AND media_url IS NULL)"
            " OR (message_type IN ('image','audio') AND media_url IS NOT NULL)",
            name="ck_ai_conversation_items_content",
        ),
        CheckConstraint(
            "(role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user')",
            name="ck_ai_conversation_items_user_buffer",
        ),
    )


class AIConversationState(Base, TimestampMixin):
    """Per-conversation transient state (pending AI messages, interruption metadata)."""

    __tablename__ = "ai_conversation_state"

    user_qiao_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_qiao_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    pending_messages: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Pending messages structure: {"outgoing": [...], "total_pending": N}',
    )
    interrupted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the last interruption occurred",
    )

    __table_args__ = (Index("idx_ai_conversation_state_updated", "updated_at"),)


class AIConversationRuntime(Base, TimestampMixin):
    """Per-conversation runtime turn versions for delayed preemption."""

    __tablename__ = "ai_conversation_runtime"

    user_qiao_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_qiao_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ingress_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Inbound turn version incremented on each CONTENT_INPUT event",
    )
    active_turn_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Active processing turn version switched on successful LOCKED acquisition",
    )

    __table_args__ = (Index("idx_ai_conversation_runtime_updated", "updated_at"),)


class AIConversationItemArchive(ImmutableSnowflakeModel):
    """Archived conversation rows for cold storage (immutable)."""

    __tablename__ = "ai_conversation_items_archive"

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )
    instance_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Instance external ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Message role: system/user/assistant"
    )
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default=text("'text'"),
        comment="Message type: text/image/audio",
    )
    text_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text content (for message_type=text)",
    )
    media_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Media URL for image/audio messages",
    )
    media_metadata: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Media metadata (dimensions, transcript, duration, etc.)",
    )
    client_msg_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
        comment="Client message IDs merged into this row",
    )
    buffer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated buffer ID (references ai_message_buffer.id, no FK constraint)",
    )
    is_excluded_from_context: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Context inclusion status: 0=included, 1=excluded (prompt injection, etc.)",
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Archive timestamp"
    )

    __table_args__ = (
        Index(
            "idx_ai_conv_items_archive_session", "user_qiao_id", "instance_qiao_id", "created_at"
        ),
    )
