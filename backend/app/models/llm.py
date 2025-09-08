"""
LLM provider and configuration models.

This module contains SQLAlchemy models for LLM provider management.
"""

from typing import Optional
from sqlalchemy import Integer, String, Boolean, DECIMAL, Text
from sqlalchemy.orm import Mapped, mapped_column

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

    api_key_env: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Environment variable name for API key"
    )

    default_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Default model name"
    )

    supports_streaming: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Supports streaming output"
    )

    supports_json_schema: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Supports JSON schema"
    )

    supports_thinking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Supports thinking mode"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Status: 1=active, 2=inactive",
    )


class LLMConfig(AutoIncrementModel):
    """
    LLM configuration model.

    Manages runtime configuration for LLM providers.
    """

    __tablename__ = "llm_configs"

    provider_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Provider ID, references llm_providers.id"
    )

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

    enable_streaming: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Enable streaming output"
    )

    enable_thinking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Enable thinking mode"
    )

    json_schema_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto", comment="JSON schema mode: auto, strict, disabled"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Is configuration active"
    )

    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Priority for failover (lower number = higher priority)"
    )
