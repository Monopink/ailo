"""AI request log related models.

This module contains SQLAlchemy models for AI service request logging.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.models.base import ImmutableSnowflakeModel
from app.type_defs import JSONDict

if TYPE_CHECKING:
    from app.models.ai.instance import AIInstance, AIMessageBuffer
    from app.models.ai.personality import AIPersonality
    from app.models.ai.style import AIStyle
    from app.models.llm.config import LLMConfig
    from app.models.user import User


class AIRequestLog(ImmutableSnowflakeModel):
    """AI request log model.

    AI service request logging.
    AI request logs are immutable - no updated_at field needed.
    """

    __tablename__ = "ai_request_logs"

    instance_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Instance ID, references ai_instances.id"
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="User ID, references users.id"
    )

    user_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="User external ID"
    )

    style_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Style ID, references ai_styles.id"
    )

    personality_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Personality ID, references ai_personalities.id"
    )

    request_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="production",
        server_default=text("'production'"),
        comment="Request type enum (see app.enums.AIRequestType)",
    )

    provider_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="LLM provider name (doubao, openai, etc.)"
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Model name used for the request"
    )

    llm_config_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="LLM config ID used for this request"
    )

    response_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Provider response ID (for caching trace)"
    )

    cache_hit: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Whether the provider reported cached tokens",
    )

    buffer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Associated ai_message_buffer.id that triggered the request",
    )

    instance: Mapped["AIInstance | None"] = orm_relationship(
        "AIInstance",
        primaryjoin="AIRequestLog.instance_id == AIInstance.id",
        foreign_keys="[AIRequestLog.instance_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    user: Mapped["User | None"] = orm_relationship(
        "User",
        primaryjoin="AIRequestLog.user_id == User.id",
        foreign_keys="[AIRequestLog.user_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    style: Mapped["AIStyle | None"] = orm_relationship(
        "AIStyle",
        primaryjoin="AIRequestLog.style_id == AIStyle.id",
        foreign_keys="[AIRequestLog.style_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    personality: Mapped["AIPersonality | None"] = orm_relationship(
        "AIPersonality",
        primaryjoin="AIRequestLog.personality_id == AIPersonality.id",
        foreign_keys="[AIRequestLog.personality_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    llm_config: Mapped["LLMConfig | None"] = orm_relationship(
        "LLMConfig",
        primaryjoin="AIRequestLog.llm_config_id == LLMConfig.id",
        foreign_keys="[AIRequestLog.llm_config_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    buffer: Mapped["AIMessageBuffer | None"] = orm_relationship(
        "AIMessageBuffer",
        primaryjoin="AIRequestLog.buffer_id == AIMessageBuffer.id",
        foreign_keys="[AIRequestLog.buffer_id]",
        lazy="select",
        viewonly=True,
        uselist=False,
    )

    request: Mapped[JSONDict] = mapped_column(JSONB, nullable=False, comment="Request content")

    response: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Response content"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Request status enum (see app.enums.AIRequestStatus)",
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Token consumption"
    )

    response_time: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    # Timestamps (created_at inherited from ImmutableSnowflakeModel)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Request completion timestamp"
    )
