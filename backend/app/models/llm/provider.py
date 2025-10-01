"""
LLM provider model.

This module contains the LLMProvider SQLAlchemy model.
"""

from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import AutoIncrementModel

if TYPE_CHECKING:
    from .config import LLMConfig


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
