"""
LLM configuration model.

This module contains the LLMConfig SQLAlchemy model.
"""

from typing import TYPE_CHECKING, Any

from models.base import AutoIncrementModel
from sqlalchemy import DECIMAL, Boolean, CheckConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
        String(50),
        nullable=False,
        unique=True,
        comment="Configuration name (primary, backup, test, etc.)",
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Specific model name (optional)"
    )

    temperature: Mapped[float | None] = mapped_column(
        DECIMAL(3, 2),
        nullable=True,
        comment="Temperature parameter (0.0-2.0)",
    )

    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Maximum tokens")

    timeout_seconds: Mapped[int | None] = mapped_column(
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

    stop_sequences: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Stop sequences (max 4 strings). Model stops when encountering these strings.",
    )

    json_schema_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="JSON Schema support status: strict=verified supported, disabled=verified not supported, auto=not verified",
    )

    default_tools: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Default tool definitions (JSON array)",
    )

    default_tool_choice: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="auto",
        server_default=text("'auto'"),
        comment="Tool choice behavior for the provider (auto/none/required)",
    )

    parallel_tool_calls: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Allow the provider to execute tools in parallel",
    )

    max_tool_calls: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="Maximum number of tool calls per request",
    )

    default_extra_headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Default extra headers passed to the provider",
    )

    default_extra_query: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Default query parameters passed to the provider",
    )

    enable_streaming: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Enable streaming output (experimental, default: false)",
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

    extra_params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific parameters (e.g., max_completion_tokens, service_tier)",
    )

    # Indexes and constraints
    __table_args__ = (
        Index("idx_llm_configs_provider_id", "provider_id"),
        CheckConstraint(
            "thinking_mode IN ('enabled', 'disabled', 'auto')", name="check_thinking_mode"
        ),
        CheckConstraint("top_p >= 0 AND top_p <= 1", name="check_top_p"),
        CheckConstraint(
            "frequency_penalty >= -2 AND frequency_penalty <= 2", name="check_frequency_penalty"
        ),
        CheckConstraint(
            "presence_penalty >= -2 AND presence_penalty <= 2", name="check_presence_penalty"
        ),
        CheckConstraint(
            "default_tool_choice IN ('auto', 'none', 'required')",
            name="check_default_tool_choice",
        ),
        CheckConstraint("max_tool_calls >= 0", name="check_max_tool_calls"),
    )
