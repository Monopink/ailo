"""
LLM configuration model.

This module contains the LLMConfig SQLAlchemy model.
"""

from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import Integer, String, DECIMAL, Index, text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel

if TYPE_CHECKING:
    from .provider import LLMProvider


class LLMConfig(AutoIncrementModel):
    """
    LLM configuration model.

    Manages runtime configuration for LLM providers.
    """

    __tablename__ = "llm_configs"

    provider_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Provider ID, references llm_providers.id",
    )

    # Relationship to provider
    provider: Mapped["LLMProvider"] = relationship(
        "LLMProvider",
        back_populates="configs",
        primaryjoin="foreign(LLMConfig.provider_id) == LLMProvider.id",
    )

    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="Configuration name (primary, backup, test, etc.)"
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Specific model name (optional)"
    )

    temperature: Mapped[Optional[float]] = mapped_column(
        DECIMAL(3, 2),
        nullable=True,
        comment="Temperature parameter (0.0-2.0)",
    )

    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Maximum tokens")

    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Timeout in seconds"
    )

    thinking_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="auto",
        server_default=text("'auto'"),
        comment="Thinking mode: enabled=force on, disabled=force off, auto=let model decide",
    )

    top_p: Mapped[float] = mapped_column(
        DECIMAL(3, 2),
        nullable=False,
        default=0.70,
        server_default=text("0.70"),
        comment="Nucleus sampling threshold [0, 1]. Controls diversity of output.",
    )

    frequency_penalty: Mapped[float] = mapped_column(
        DECIMAL(3, 2),
        nullable=False,
        default=0.00,
        server_default=text("0.00"),
        comment="Frequency penalty [-2, 2]. Reduces repetition based on token frequency.",
    )

    presence_penalty: Mapped[float] = mapped_column(
        DECIMAL(3, 2),
        nullable=False,
        default=0.00,
        server_default=text("0.00"),
        comment="Presence penalty [-2, 2]. Encourages new topics based on token presence.",
    )

    stop_sequences: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Stop sequences (max 4 strings). Model stops when encountering these strings.",
    )

    json_schema_mode: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="JSON Schema support status: strict=verified supported, disabled=verified not supported, auto=not verified",
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Status: 1=active, 2=inactive",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Priority for failover (lower number = higher priority)",
    )

    extra_params: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Provider-specific parameters (e.g., max_completion_tokens, service_tier)"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("idx_llm_configs_provider_id", "provider_id"),
        CheckConstraint("thinking_mode IN ('enabled', 'disabled', 'auto')", name="check_thinking_mode"),
        CheckConstraint("top_p >= 0 AND top_p <= 1", name="check_top_p"),
        CheckConstraint("frequency_penalty >= -2 AND frequency_penalty <= 2", name="check_frequency_penalty"),
        CheckConstraint("presence_penalty >= -2 AND presence_penalty <= 2", name="check_presence_penalty"),
    )
