"""
LLM provider and configuration models.

This module contains SQLAlchemy models for LLM provider management.
"""

from typing import Optional
from sqlalchemy import Integer, String, DECIMAL, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import AutoIncrementModel


class LLMProvider(AutoIncrementModel):
    """
    LLM provider model.

    Manages different LLM providers like Doubao, OpenAI, Claude, etc.
    """

    __tablename__ = "llm_providers"

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Provider identifier (doubao, openai, claude, etc.)",
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Display name for UI"
    )

    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="API base URL")

    default_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Default model name"
    )

    supports_streaming: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Supports streaming output: 1=yes, 0=no"
    )

    supports_json_schema: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Supports JSON schema: 1=yes, 0=no"
    )

    supports_thinking: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Supports thinking mode: 1=yes, 0=no"
    )

    # Relationship to configs
    configs: Mapped[list["LLMConfig"]] = relationship("LLMConfig", back_populates="provider")


class LLMConfig(AutoIncrementModel):
    """
    LLM configuration model.

    Manages runtime configuration for LLM providers.
    """

    __tablename__ = "llm_configs"

    provider_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("llm_providers.id"),
        nullable=False,
        comment="Provider ID, references llm_providers.id",
    )

    # Relationship to provider
    provider: Mapped["LLMProvider"] = relationship("LLMProvider", back_populates="configs")

    config_key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, comment="Configuration key (primary, backup, test, etc.)"
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Specific model name (optional)"
    )

    temperature: Mapped[Optional[float]] = mapped_column(
        DECIMAL(3, 2), nullable=True, default=0.7, comment="Temperature parameter (0.0-2.0)"
    )

    max_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=2000, comment="Maximum tokens"
    )

    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, comment="Timeout in seconds"
    )

    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="Maximum retry attempts"
    )

    enable_streaming: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Enable streaming output: 1=yes, 0=no"
    )

    enable_thinking: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Enable thinking mode: 1=yes, 0=no"
    )

    json_schema_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto", comment="JSON schema mode: auto, strict, disabled"
    )

    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )

    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Priority for failover (lower number = higher priority)"
    )

    extra_params: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Additional configuration parameters in JSON format"
    )
