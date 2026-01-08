"""Protocols that describe shared fields on SQLAlchemy models.

These structural types are used purely for type checking so that the CRUD layer
can safely access attributes like ``id`` or ``status`` without tripping
Pylance/mypy. They intentionally keep a narrow surface area to reduce coupling.
"""

from __future__ import annotations

from typing import Any, Protocol


class IdModelProtocol(Protocol):
    """Model with an integer or Snowflake-based primary key.

    For SQLAlchemy models, class-level access (e.g., ``Model.id``) returns an
    instrumented attribute rather than the runtime Python type. We therefore
    keep the annotation as ``Any`` to satisfy SQLAlchemy's expectations while
    still documenting the concept semantically.
    """

    id: Any


class QiaoIdModelProtocol(IdModelProtocol, Protocol):
    """Model that exposes the external-facing qiao_id."""

    qiao_id: Any


class StatusModelProtocol(IdModelProtocol, Protocol):
    """Model that stores a status flag."""

    status: Any


class ImmutableModelProtocol(IdModelProtocol, Protocol):
    """Immutable log model that stores creation timestamp."""

    created_at: Any
