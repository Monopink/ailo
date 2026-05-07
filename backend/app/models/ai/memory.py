from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.models.base import SnowflakeModel

if TYPE_CHECKING:
    from app.models.ai.instance import AIInstance
    from app.models.ai.template import AITemplate
    from app.models.user import User


class AITemplateMemory(SnowflakeModel):
    """Seed memories defined on templates."""

    __tablename__ = "ai_template_memories"

    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_templates.id", ondelete="CASCADE"), nullable=False
    )
    template: Mapped["AITemplate"] = orm_relationship(
        "AITemplate",
        primaryjoin="AITemplate.id == foreign(AITemplateMemory.template_id)",
        lazy="select",
    )
    memory_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Memory type enum (see app.enums.MemoryType)",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Memory description")
    importance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
        comment="Importance 1-10, determines lifetime",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Copy order when instantiating templates",
    )

    __table_args__ = (
        CheckConstraint("memory_type IN ('core','recent')", name="ck_template_memories_type"),
        CheckConstraint(
            "importance BETWEEN 1 AND 10", name="ck_template_memories_importance_range"
        ),
        Index("idx_template_memories_template", "template_id", "display_order"),
    )


class AIInstanceMemory(SnowflakeModel):
    """Runtime memories associated with AI instances."""

    __tablename__ = "ai_instance_memories"

    instance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_instances.id", ondelete="CASCADE"), nullable=False
    )
    instance_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Memory type enum (see app.enums.MemoryType)",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Memory description")
    normalized_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
        comment="Normalized content used for deduplication",
    )
    importance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
        comment="Importance 1-10, determines lifetime",
    )
    reinforce_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Reinforcement count for merged/recalled memories",
    )
    last_reinforced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last reinforcement timestamp",
    )
    source_strength: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Source strength rank (1-5)",
    )
    fact_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Rule-based fact key for conservative conflict handling",
    )
    conflict_flag: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Conflict resolution marker",
    )
    refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Last refresh timestamp"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Pre-calculated expiration timestamp"
    )
    source_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Source conversation item ID"
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status enum (see app.enums.AIInstanceMemoryStatus)",
    )

    instance: Mapped["AIInstance"] = orm_relationship(
        "AIInstance",
        primaryjoin="AIInstance.id == foreign(AIInstanceMemory.instance_id)",
        lazy="select",
    )
    user: Mapped["User"] = orm_relationship(
        "User",
        primaryjoin="User.id == foreign(AIInstanceMemory.user_id)",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint("memory_type IN ('core','recent')", name="ck_instance_memories_type"),
        CheckConstraint(
            "importance BETWEEN 1 AND 10", name="ck_instance_memories_importance_range"
        ),
        CheckConstraint(
            "source_strength BETWEEN 1 AND 5", name="ck_instance_memories_source_strength_range"
        ),
        CheckConstraint("status IN (1,2)", name="ck_instance_memories_status"),
        Index("idx_ai_instance_memories_session", "user_qiao_id", "instance_qiao_id", "status"),
        Index("idx_ai_instance_memories_instance_id", "instance_id"),
        Index(
            "idx_ai_instance_memories_expires",
            "memory_type",
            "status",
            "expires_at",
            postgresql_where=text("memory_type = 'recent' AND status = 1"),
        ),
        Index(
            "idx_ai_instance_memories_source",
            "source_message_id",
            postgresql_where=text("source_message_id IS NOT NULL"),
        ),
        Index(
            "idx_ai_instance_memories_fact_key_active",
            "instance_id",
            "fact_key",
            postgresql_where=text("status = 1 AND fact_key IS NOT NULL"),
        ),
        Index(
            "idx_ai_instance_memories_norm_active",
            "instance_id",
            "normalized_content",
            postgresql_where=text("status = 1"),
        ),
        Index(
            "idx_ai_instance_memories_norm_trgm",
            "normalized_content",
            postgresql_using="gin",
            postgresql_ops={"normalized_content": "gin_trgm_ops"},
        ),
        Index(
            "uq_ai_instance_memory_active_norm",
            "instance_id",
            "normalized_content",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
