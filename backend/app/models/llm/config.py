"""
LLM configuration model.

This module contains the LLMConfig SQLAlchemy model.
"""

from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, DECIMAL, Index, text
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

    config_key: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="Configuration key (primary, backup, test, etc.)"
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

    max_retries: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Maximum retry attempts"
    )

    enable_streaming: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Enable streaming output: 1=yes, 0=no",
    )

    enable_thinking: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Enable thinking mode: 1=yes, 0=no",
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
        JSONB, nullable=True, comment="Additional configuration parameters in JSON format"
    )

    # Indexes - Only essential indexes for MVP
    # Note: config_key already has unique index
    __table_args__ = (Index("idx_llm_configs_provider_id", "provider_id"),)
