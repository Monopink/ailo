"""Invite code related models."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AutoIncrementModel, ImmutableAutoIncrementModel


class InviteCode(AutoIncrementModel):
    """User invite code entity."""

    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(
        String(6), nullable=False, unique=True, comment="Global unique user invite code"
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Owner user id for invite code",
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )

    owner_user = relationship("User", foreign_keys=[owner_user_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_invite_codes_status"),
        CheckConstraint("char_length(code) = 6", name="ck_invite_codes_code_len"),
        CheckConstraint("code ~ '^[A-Z0-9]{6}$'", name="ck_invite_codes_code_format"),
        UniqueConstraint("code", name="uq_invite_codes_code"),
        UniqueConstraint("owner_user_id", name="uq_invite_codes_owner_user_id"),
        UniqueConstraint("id", "code", name="uq_invite_codes_id_code"),
        UniqueConstraint("id", "owner_user_id", name="uq_invite_codes_id_owner"),
        Index("idx_invite_codes_status", "status"),
    )


class InviteBinding(AutoIncrementModel):
    """Invite code binding for a user."""

    __tablename__ = "invite_bindings"

    invitee_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Invitee user id (bind once)",
    )
    invite_code_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invite_codes.id", ondelete="RESTRICT"), nullable=False
    )
    code_snapshot: Mapped[str] = mapped_column(String(6), nullable=False, comment="Code snapshot")
    inviter_user_id_snapshot: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Inviter user id snapshot",
    )

    invitee_user = relationship("User", foreign_keys=[invitee_user_id], lazy="raise", viewonly=True)
    inviter_user = relationship(
        "User",
        foreign_keys=[inviter_user_id_snapshot],
        lazy="raise",
        viewonly=True,
    )
    invite_code = relationship(
        "InviteCode", foreign_keys=[invite_code_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint("char_length(code_snapshot) = 6", name="ck_invite_bindings_code_len"),
        CheckConstraint(
            "code_snapshot ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_bindings_code_format",
        ),
        ForeignKeyConstraint(
            ["invite_code_id", "code_snapshot"],
            ["invite_codes.id", "invite_codes.code"],
            ondelete="RESTRICT",
            name="fk_invite_bindings_code_snapshot_consistent",
        ),
        ForeignKeyConstraint(
            ["invite_code_id", "inviter_user_id_snapshot"],
            ["invite_codes.id", "invite_codes.owner_user_id"],
            ondelete="RESTRICT",
            name="fk_invite_bindings_inviter_snapshot_consistent",
        ),
        UniqueConstraint("invitee_user_id", name="uq_invite_bindings_invitee"),
        Index("idx_invite_bindings_invite_code_id", "invite_code_id"),
        Index("idx_invite_bindings_inviter_user", "inviter_user_id_snapshot"),
    )


class InviteEvent(ImmutableAutoIncrementModel):
    """Invite event log for metrics and audit."""

    __tablename__ = "invite_events"

    event_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1=open,2=resolve_valid,3=bind_success,4=copy_command,5=share_wechat",
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invite_code_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invite_codes.id", ondelete="SET NULL"), nullable=True
    )
    event_source: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    code_snapshot: Mapped[str | None] = mapped_column(String(6), nullable=True)
    event_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    actor_user = relationship("User", foreign_keys=[actor_user_id], lazy="raise", viewonly=True)
    invite_code = relationship(
        "InviteCode", foreign_keys=[invite_code_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint("event_type IN (1, 2, 3, 4, 5)", name="ck_invite_events_event_type"),
        CheckConstraint(
            "event_source IN ('login', 'setup', 'link', "
            "'invite_bind_page', 'invite_share_page', 'unknown')",
            name="ck_invite_events_event_source",
        ),
        CheckConstraint(
            "code_snapshot IS NULL OR code_snapshot ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_events_code_snapshot_format",
        ),
        Index("idx_invite_events_code_event_time", "invite_code_id", "event_type", "created_at"),
        Index("idx_invite_events_actor_event_time", "actor_user_id", "event_type", "created_at"),
        Index("idx_invite_events_type_time", "event_type", "created_at"),
    )


class InviteIntakeLog(ImmutableAutoIncrementModel):
    """Invite intake log for clipboard/link/manual input analysis."""

    __tablename__ = "invite_intake_logs"

    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    first_candidate: Mapped[str | None] = mapped_column(String(6), nullable=True)
    recognized_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    invite_code_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invite_codes.id", ondelete="SET NULL"), nullable=True
    )
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bindable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reviewer_flag_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    runtime_observation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("client_runtime_observations.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_user_agent: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    client_device_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    actor_user = relationship("User", foreign_keys=[actor_user_id], lazy="raise", viewonly=True)
    invite_code = relationship(
        "InviteCode", foreign_keys=[invite_code_id], lazy="raise", viewonly=True
    )
    runtime_observation = relationship(
        "ClientRuntimeObservation",
        foreign_keys=[runtime_observation_id],
        lazy="raise",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('login', 'setup', 'link', 'invite_bind_page', 'invite_share_page')",
            name="ck_invite_intake_logs_source",
        ),
        CheckConstraint(
            "trigger ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_invite_intake_logs_trigger_format",
        ),
        CheckConstraint(
            "first_candidate IS NULL OR first_candidate ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_intake_logs_first_candidate_format",
        ),
        CheckConstraint(
            "recognized_code IS NULL OR recognized_code ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_intake_logs_recognized_code_format",
        ),
        CheckConstraint(
            "reviewer_flag_snapshot IN (0, 1)",
            name="ck_invite_intake_logs_reviewer_flag_snapshot",
        ),
        Index("idx_invite_intake_logs_created_at", "created_at"),
        Index("idx_invite_intake_logs_source_created_at", "source", "created_at"),
        Index("idx_invite_intake_logs_recognized_code", "recognized_code"),
        Index("idx_invite_intake_logs_runtime_observation", "runtime_observation_id"),
        Index("idx_invite_intake_logs_device_created_at", "client_device_id", "created_at"),
    )


# Compatibility alias for modules that are not migrated yet.
InviteRecognitionLog = InviteIntakeLog
