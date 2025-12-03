"""
System configuration related models.

This module contains SQLAlchemy models for system configuration management.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AutoIncrementModel


class SystemConfig(AutoIncrementModel):
    """
    System configuration model.

    System-wide configuration parameters.
    """

    __tablename__ = "system_configs"

    config_key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, comment="Configuration key"
    )

    config_value: Mapped[str] = mapped_column(Text, nullable=False, comment="Configuration value")

    default_value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Default configuration value"
    )

    config_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Value type: 1=string, 2=number, 3=boolean, 4=json"
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Configuration description"
    )

    updated_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Updated by admin user ID"
    )

    group_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="分组名称，用于显示分组"
    )

    allowed_values: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="Allowed values for enum type (JSON array)"
    )
