"""
Contact management related models.

This module contains SQLAlchemy models for contact relationships and requests.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, Index, UniqueConstraint, and_, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from enums import ContactType, ContactRequestSource, ContactRequestStatus
from models.base import SnowflakeModel, SoftDeleteMixin

if TYPE_CHECKING:
    from models.user import User
    from models.ai.character import AICharacter


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

    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, comment="Contact tags (JSONB)")

    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Contact remark/notes")

    is_pinned: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Is pinned: 1=yes, 0=no"
    )

    is_muted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Is muted: 1=yes, 0=no"
    )

    is_blocked: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"), comment="Is blocked: 1=yes, 0=no"
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="Contact.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )

    # Polymorphic contact relationships
    _contact_user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="and_(Contact.contact_id == User.id, Contact.contact_type == 1)",
        foreign_keys=[contact_id],
        lazy="select",
        viewonly=True,
    )
    _contact_character: Mapped[Optional["AICharacter"]] = relationship(
        "AICharacter",
        primaryjoin="and_(Contact.contact_id == AICharacter.id, Contact.contact_type == 2)",
        foreign_keys=[contact_id],
        lazy="select",
        viewonly=True,
    )

    @hybrid_property
    def contact(self):
        """Return the appropriate contact object based on contact_type."""
        if self.contact_type == 1:  # User
            return self._contact_user
        elif self.contact_type == 2:  # AI Character
            return self._contact_character
        return None

    # Indexes - Only essential indexes for MVP
    # Note: conv_id already has unique index
    __table_args__ = (
        Index("idx_contacts_user_qiao_id", "user_qiao_id"),
        Index("idx_contacts_contact_qiao_id", "contact_qiao_id"),
        # Unique constraint: one owner can only have one contact record for each contact
        UniqueConstraint("user_id", "contact_id", "contact_type", name="contacts_user_contact_unique"),
    )


class ContactRequest(SnowflakeModel):
    """
    Contact request model.

    Manages contact addition requests and approvals.
    """

    __tablename__ = "contact_requests"

    from_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Applicant external ID")

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Applicant type: 1=user (all user types), 2=ai"
    )

    from_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Applicant internal ID")

    to_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="Target external ID")

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Target type: 1=user (all user types), 2=ai"
    )

    to_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Target internal ID")

    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Application message")

    source: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Source: 1=search, 2=admin, 3=system, 4=recommend"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ContactRequestStatus.PENDING,
        server_default=text("1"),
        comment="Status: 1=pending, 2=accepted, 3=rejected, 4=expired",
    )

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Expiration time"
    )

    # Polymorphic from relationships
    # from_type=1 (USER) → users table (includes all user types)
    _from_user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="and_(ContactRequest.from_id == User.id, ContactRequest.from_type == 1)",
        foreign_keys=[from_id],
        lazy="select",
        viewonly=True,
    )

    # from_type=2 (AI) → ai_characters table
    _from_character: Mapped[Optional["AICharacter"]] = relationship(
        "AICharacter",
        primaryjoin="and_(ContactRequest.from_id == AICharacter.id, ContactRequest.from_type == 2)",
        foreign_keys=[from_id],
        lazy="select",
        viewonly=True,
    )

    # Polymorphic to relationships
    # to_type=1 (USER) → users table (includes all user types)
    _to_user: Mapped[Optional["User"]] = relationship(
        "User",
        primaryjoin="and_(ContactRequest.to_id == User.id, ContactRequest.to_type == 1)",
        foreign_keys=[to_id],
        lazy="select",
        viewonly=True,
    )

    # to_type=2 (AI) → ai_characters table
    _to_character: Mapped[Optional["AICharacter"]] = relationship(
        "AICharacter",
        primaryjoin="and_(ContactRequest.to_id == AICharacter.id, ContactRequest.to_type == 2)",
        foreign_keys=[to_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes - Only essential indexes for MVP
    __table_args__ = (Index("idx_contact_requests_expires_at", "expires_at"),)
