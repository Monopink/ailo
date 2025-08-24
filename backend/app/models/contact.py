"""
Contact management related models.

This module contains SQLAlchemy models for contact relationships and requests.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from enums import ContactType, ContactRequestSource, ContactRequestStatus
from models.base import SnowflakeModel, SoftDeleteMixin


class Contact(SnowflakeModel, SoftDeleteMixin):
    """
    Contact relationship model.

    Manages contact relationships between users and AI characters.
    """

    __tablename__ = "contacts"

    conv_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Conversation identifier: conv_+random"
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Contact owner user ID, NULL for public contacts"
    )

    user_qiao_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Contact owner external ID, NULL for public contacts"
    )

    contact_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Contact type: 1=user, 2=ai, 3=official"
    )

    contact_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Contact internal ID")

    contact_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Contact external ID")

    alias: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Contact alias/remark name"
    )

    avatar_alias_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Custom avatar URL for this contact"
    )

    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Contact tags (JSON)")

    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Contact remark/notes")

    is_pinned: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Is pinned: 1=yes, 0=no"
    )

    is_muted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Is muted: 1=yes, 0=no"
    )

    is_blocked: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Is blocked: 1=yes, 0=no"
    )

    # Indexes
    __table_args__ = (
        Index("idx_contacts_conv_id", "conv_id"),
        Index("idx_contacts_user_id", "user_id"),
        Index("idx_contacts_user_qiao_id", "user_qiao_id"),
        Index("idx_contacts_contact_type", "contact_type"),
        Index("idx_contacts_contact_id", "contact_id"),
        Index("idx_contacts_contact_qiao_id", "contact_qiao_id"),
        Index("idx_contacts_is_pinned", "is_pinned"),
        Index("idx_contacts_is_deleted", "is_deleted"),
        Index("idx_contacts_created_at", "created_at"),
    )


class ContactRequest(SnowflakeModel):
    """
    Contact request model.

    Manages contact addition requests and approvals.
    """

    __tablename__ = "contact_requests"

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Applicant external ID")

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Applicant type: 1=user, 2=ai, 3=official"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Applicant internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Target external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Target type: 1=user, 2=ai, 3=official"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Target internal ID")

    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Application message")

    source: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Source: 1=search, 2=admin, 3=system, 4=invite"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ContactRequestStatus.PENDING,
        comment="Status: 1=pending, 2=accepted, 3=rejected, 4=expired",
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="Expiration time")

    # Indexes
    __table_args__ = (
        Index("idx_contact_requests_from_qiao_id", "from_qiao_id"),
        Index("idx_contact_requests_to_qiao_id", "to_qiao_id"),
        Index("idx_contact_requests_status", "status"),
        Index("idx_contact_requests_expires_at", "expires_at"),
        Index("idx_contact_requests_created_at", "created_at"),
    )
