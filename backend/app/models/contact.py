"""Contact management related models.

This module contains SQLAlchemy models for contact relationships and requests.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import ContactRequestStatus, ContactType
from app.models.base import SnowflakeModel, SoftDeleteMixin
from app.type_defs import JSONDict

if TYPE_CHECKING:
    from app.models.ai.instance import AIInstance
    from app.models.message import MediaFile
    from app.models.user import User


class Contact(SnowflakeModel, SoftDeleteMixin):
    """Contact relationship model.

    Manages contact relationships between users and AI instances.
    """

    __tablename__ = "contacts"

    conv_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, comment="Conversation identifier: conv_+random"
    )

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Contact owner user ID, NULL for public contacts"
    )

    user_qiao_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Contact owner external ID, NULL for public contacts"
    )

    contact_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Contact type: 1=user, 2=ai, 3=official"
    )

    contact_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Contact internal ID"
    )

    contact_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Contact external ID"
    )

    alias: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Contact alias/remark name"
    )

    custom_avatar_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment=(
            "Custom avatar object key (overrides contact's real avatar). "
            "NULL means the contact's real avatar is used."
        ),
    )

    custom_avatar_media_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to media_files.id for audit trail. NULL when using contact's real avatar",
    )

    tags: Mapped[JSONDict | None] = mapped_column(
        JSONB, nullable=True, comment="Contact tags (JSONB)"
    )

    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Contact remark/notes")

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        comment="Contact creation source (discovery/search/recommend/etc.)",
    )

    is_pinned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is pinned: 1=yes, 0=no",
    )

    is_muted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is muted: 1=yes, 0=no",
    )

    is_blocked: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Is blocked: 1=yes, 0=no",
    )

    # Relationships
    user: Mapped[User | None] = relationship(
        "User",
        primaryjoin="Contact.user_id == User.id",
        foreign_keys=[user_id],
        lazy="select",
        viewonly=True,
    )

    # Polymorphic contact relationships
    _contact_user: Mapped[User | None] = relationship(
        "User",
        primaryjoin=(
            f"and_(Contact.contact_id == User.id, Contact.contact_type == {ContactType.USER.value})"
        ),
        foreign_keys=[contact_id],
        lazy="select",
        viewonly=True,
    )
    _contact_instance: Mapped[AIInstance | None] = relationship(
        "AIInstance",
        primaryjoin=(
            "and_(Contact.contact_id == AIInstance.id, "
            f"Contact.contact_type == {ContactType.AI.value})"
        ),
        foreign_keys=[contact_id],
        lazy="select",
        viewonly=True,
    )

    # Custom avatar media file relationship
    custom_avatar_media: Mapped[MediaFile | None] = relationship(
        "MediaFile",
        primaryjoin="Contact.custom_avatar_media_id == MediaFile.id",
        foreign_keys=[custom_avatar_media_id],
        lazy="select",
        viewonly=True,
    )

    @hybrid_property
    def contact(self) -> User | AIInstance | None:
        """Return the appropriate contact object based on contact_type."""
        if self.contact_type == ContactType.USER.value:
            return self._contact_user
        if self.contact_type == ContactType.AI.value:
            return self._contact_instance
        return None

    # Indexes - Only essential indexes for MVP
    # Note: conv_id already has unique index
    __table_args__ = (
        Index("idx_contacts_user_qiao_id", "user_qiao_id"),
        Index("idx_contacts_contact_qiao_id", "contact_qiao_id"),
        # Unique constraint: one owner can only have one contact record for each contact
        UniqueConstraint("user_id", "contact_qiao_id", name="contacts_user_contact_qiao_unique"),
    )


class ContactRequest(SnowflakeModel):
    """Contact request model.

    Manages contact addition requests and approvals.
    """

    __tablename__ = "contact_requests"

    from_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Applicant external ID"
    )

    from_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Applicant type: 1=user (all user types), 2=ai"
    )

    from_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Applicant internal ID"
    )

    to_qiao_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Target external ID"
    )

    to_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Target type: 1=user (all user types), 2=ai"
    )

    to_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Target internal ID (NULL when AI instance not created yet)",
    )

    message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Application message")

    source: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Source: 1=search, 2=admin, 3=system, 4=recommend"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ContactRequestStatus.PENDING,
        server_default=text("1"),
        comment="Status: 1=pending, 2=accepted, 3=ignored, 8=processing, 9=failed",
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Failure code explaining why request is pending (e.g., NO_TEMPLATE_AVAILABLE)",
    )

    failure_detail: Mapped[JSONDict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured failure metadata (template shortage details, etc.)",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of manual/system retries for this request",
    )

    last_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp of last retry (manual or automated)",
    )

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="Expiration time"
    )

    # Polymorphic from relationships
    # from_type=1 (USER) → users table (includes all user types)
    _from_user: Mapped[User | None] = relationship(
        "User",
        primaryjoin="and_(ContactRequest.from_id == User.id, ContactRequest.from_type == 1)",
        foreign_keys=[from_id],
        lazy="select",
        viewonly=True,
    )

    # from_type=2 (AI) → ai_instances table
    _from_instance: Mapped[AIInstance | None] = relationship(
        "AIInstance",
        primaryjoin="and_(ContactRequest.from_id == AIInstance.id, ContactRequest.from_type == 2)",
        foreign_keys=[from_id],
        lazy="select",
        viewonly=True,
    )

    # Polymorphic to relationships
    # to_type=1 (USER) → users table (includes all user types)
    _to_user: Mapped[User | None] = relationship(
        "User",
        primaryjoin="and_(ContactRequest.to_id == User.id, ContactRequest.to_type == 1)",
        foreign_keys=[to_id],
        lazy="select",
        viewonly=True,
    )

    # to_type=2 (AI) → ai_instances table
    _to_instance: Mapped[AIInstance | None] = relationship(
        "AIInstance",
        primaryjoin="and_(ContactRequest.to_id == AIInstance.id, ContactRequest.to_type == 2)",
        foreign_keys=[to_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes - Only essential indexes for MVP
    __table_args__ = (Index("idx_contact_requests_expires_at", "expires_at"),)
