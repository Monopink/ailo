"""
LLM request log model.

This module defines the database model for logging LLM requests
during testing and monitoring.
"""

from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from .base import AutoIncrementModel
from enums import LLMRequestStatus


class LLMRequestLog(AutoIncrementModel):
    """
    LLM request log model.

    Logs all LLM requests for testing, monitoring, and debugging purposes.
    """

    __tablename__ = "llm_request_logs"

    request_id: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="Unique request identifier"
    )

    test_session_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Test session identifier for grouping related requests"
    )

    character_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Character's qiao_id involved in the request"
    )

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="User's qiao_id involved in the request"
    )

    provider_name: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="LLM provider name (doubao, openai, etc.)"
    )

    config_key: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="LLM config key used for the request"
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Model name used for the request"
    )

    request_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="real", comment="Request type: real, simulated, test"
    )

    request_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Request payload sent to LLM"
    )

    response_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Response received from LLM"
    )

    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Response time in milliseconds"
    )

    token_usage: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="Token usage information"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=LLMRequestStatus.PENDING,
        comment="Request status: 1=pending, 2=success, 3=error",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error message if request failed"
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Request completion timestamp"
    )

    def __repr__(self) -> str:
        return f"<LLMRequestLog(request_id='{self.request_id}', status='{self.status}')>"

    @property
    def is_completed(self) -> bool:
        """Check if the request is completed (success or error)."""
        return self.status in ("success", "error")

    @property
    def is_successful(self) -> bool:
        """Check if the request was successful."""
        return self.status == "success"

    @property
    def duration_ms(self) -> Optional[int]:
        """Get request duration in milliseconds."""
        return self.response_time_ms

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "test_session_id": self.test_session_id,
            "character_qiao_id": self.character_qiao_id,
            "user_qiao_id": self.user_qiao_id,
            "provider_name": self.provider_name,
            "config_key": self.config_key,
            "model_name": self.model_name,
            "request_type": self.request_type,
            "status": self.status,
            "response_time_ms": self.response_time_ms,
            "token_usage": self.token_usage,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_detailed_dict(self) -> Dict[str, Any]:
        """Convert to detailed dictionary including request/response data."""
        result = self.to_dict()
        result.update(
            {
                "request_data": self.request_data,
                "response_data": self.response_data,
            }
        )
        return result
