"""Invite code related models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
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


class InviteRecognitionLog(ImmutableAutoIncrementModel):
    """Invite recognition log for clipboard/link recognition analysis."""

    __tablename__ = "invite_recognition_logs"

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

    actor_user = relationship("User", foreign_keys=[actor_user_id], lazy="raise", viewonly=True)
    invite_code = relationship(
        "InviteCode", foreign_keys=[invite_code_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('login', 'setup', 'link', 'invite_bind_page', 'invite_share_page')",
            name="ck_invite_recognition_logs_source",
        ),
        CheckConstraint(
            "trigger ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_invite_recognition_logs_trigger_format",
        ),
        CheckConstraint(
            "first_candidate IS NULL OR first_candidate ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_recognition_logs_first_candidate_format",
        ),
        CheckConstraint(
            "recognized_code IS NULL OR recognized_code ~ '^[A-Z0-9]{6}$'",
            name="ck_invite_recognition_logs_recognized_code_format",
        ),
        Index("idx_invite_recognition_logs_created_at", "created_at"),
        Index("idx_invite_recognition_logs_source_created_at", "source", "created_at"),
        Index("idx_invite_recognition_logs_recognized_code", "recognized_code"),
    )


class InviteShareTemplate(AutoIncrementModel):
    """Invite share template managed as structured data."""

    __tablename__ = "invite_share_templates"

    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_invite_share_templates_status"),
        CheckConstraint(
            "locale ~ '^[a-z]{2}(\\-[A-Z]{2})?$'",
            name="ck_invite_share_templates_locale_format",
        ),
        Index("idx_invite_share_templates_status_priority", "status", "priority", "id"),
        Index("idx_invite_share_templates_locale", "locale"),
    )


class OperationAsset(AutoIncrementModel):
    """Operation asset metadata for configurable share cards."""

    __tablename__ = "operation_assets"

    asset_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    media_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media_files.id", ondelete="SET NULL"), nullable=True
    )
    asset_type: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Asset type: 1=image"
    )
    cdn_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    media_file = relationship(
        "MediaFile", foreign_keys=[media_file_id], lazy="raise", viewonly=True
    )

    __table_args__ = (
        CheckConstraint("asset_type IN (1)", name="ck_operation_assets_asset_type"),
        CheckConstraint("status IN (1, 2)", name="ck_operation_assets_status"),
        CheckConstraint("version > 0", name="ck_operation_assets_version_positive"),
        CheckConstraint("cdn_url ~ '^https://'", name="ck_operation_assets_cdn_url_https"),
        CheckConstraint("width IS NULL OR width > 0", name="ck_operation_assets_width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="ck_operation_assets_height_positive"),
        UniqueConstraint("asset_code", name="uq_operation_assets_asset_code"),
        Index("idx_operation_assets_status", "status"),
        Index("idx_operation_assets_media_file", "media_file_id"),
    )


class OperationSlotConfig(AutoIncrementModel):
    """Slot-level material configuration for operation surfaces."""

    __tablename__ = "operation_slot_configs"

    slot_code: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    path_template: Mapped[str] = mapped_column(String(512), nullable=False)
    asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("operation_assets.id", ondelete="RESTRICT"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Status: 1=active, 2=inactive"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )

    asset = relationship("OperationAsset", foreign_keys=[asset_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint("status IN (1, 2)", name="ck_operation_slot_configs_status"),
        CheckConstraint(
            "slot_code ~ '^[a-z0-9_\\-]{1,64}$'",
            name="ck_operation_slot_configs_slot_code_format",
        ),
        CheckConstraint(
            "channel ~ '^[a-z0-9_\\-]{1,32}$'",
            name="ck_operation_slot_configs_channel_format",
        ),
        CheckConstraint("path_template ~ '^/.+'", name="ck_operation_slot_configs_path_template"),
        CheckConstraint("version > 0", name="ck_operation_slot_configs_version_positive"),
        CheckConstraint(
            "end_at IS NULL OR start_at IS NULL OR end_at > start_at",
            name="ck_operation_slot_configs_time_range",
        ),
        UniqueConstraint(
            "slot_code",
            "channel",
            "version",
            name="uq_operation_slot_configs_slot_channel_version",
        ),
        Index(
            "idx_operation_slot_configs_lookup",
            "slot_code",
            "channel",
            "status",
            "priority",
            "id",
        ),
        Index("idx_operation_slot_configs_time", "start_at", "end_at"),
    )


class OperationPublishLog(ImmutableAutoIncrementModel):
    """Immutable publish and rollback audit logs for operation slots."""

    __tablename__ = "operation_publish_logs"

    slot_code: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    operator = relationship("AdminUser", foreign_keys=[operator_id], lazy="raise", viewonly=True)

    __table_args__ = (
        CheckConstraint(
            "action IN ('publish', 'rollback')", name="ck_operation_publish_logs_action"
        ),
        CheckConstraint(
            "from_version IS NULL OR from_version > 0",
            name="ck_operation_publish_logs_from_version_positive",
        ),
        CheckConstraint("to_version > 0", name="ck_operation_publish_logs_to_version_positive"),
        Index("idx_operation_publish_logs_slot_time", "slot_code", "created_at"),
    )
