"""Invitation related schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.enums.invite import InviteResolveCodeType
from app.schemas.common import BaseSchema

InvitationSource = Literal["login", "setup", "link", "invite_bind_page", "invite_share_page"]


class InvitationCodeResponse(BaseSchema):
    """Response payload for current user's invite code."""

    code: str = Field(..., description="User invite code (6 chars)")


class InvitationBindingStatusResponse(BaseSchema):
    """Response payload for current user's invite binding status."""

    is_bound: bool = Field(..., description="Whether current user has bound invite code")


class InvitationStatsResponse(BaseSchema):
    """Response payload for invitation stats of current user."""

    success_invite_count: int = Field(..., ge=0, description="Successful invitee count")
    max_invite_count: int | None = Field(
        default=None,
        ge=1,
        description="Maximum invitee count allowed for inviter, null means unlimited",
    )
    reward_contact_limit_per_invite: int = Field(
        ...,
        ge=0,
        description="Contact limit reward delta for inviter on each successful invite",
    )
    max_reward_contact_limit_total: int | None = Field(
        default=None,
        ge=0,
        description="Maximum total contact limit reward for inviter, null means unlimited",
    )
    rewarded_contact_limit_total: int = Field(
        ...,
        ge=0,
        description="Current total rewarded contact limit for inviter",
    )


class InvitationResolveRequest(BaseModel):
    """Resolve invite code request payload."""

    code: str = Field(..., min_length=6, max_length=6, description="Invite code")
    source: InvitationSource = Field(
        ...,
        description="Event source tag (login/setup/link/invite_bind_page/invite_share_page)",
    )


class InvitationResolveResponse(BaseSchema):
    """Resolve invite code response payload."""

    valid: bool = Field(..., description="Whether the invite code exists and is active")
    code_type: InviteResolveCodeType | None = Field(None, description="Resolved code type")
    bindable: bool = Field(..., description="Whether current user can bind this code now")


class InvitationBindRequest(BaseModel):
    """Bind invite code request payload."""

    code: str = Field(..., min_length=6, max_length=6, description="Invite code")
    source: InvitationSource = Field(
        ...,
        description="Event source tag (login/setup/link/invite_bind_page/invite_share_page)",
    )


class InvitationBindResponse(BaseSchema):
    """Bind invite code response payload (applied deltas)."""

    code_type: InviteResolveCodeType = Field(..., description="Bound code type (user)")
    reward_contact_limit: int = Field(
        ..., description="Invitee reward delta applied to ai contact limit (>=0)"
    )


class InvitationShareCard(BaseSchema):
    """Share card payload configured by operation slot."""

    title: str = Field(..., description="Share card title")
    path: str = Field(..., description="Mini program path for share card")
    image_url: str = Field(..., description="Public share card image URL")
    slot_code: str = Field(..., description="Operation slot code")
    channel: str = Field(..., description="Share channel key")
    version: int = Field(..., ge=1, description="Slot config version")


class InvitationShareFullResponse(BaseSchema):
    """Invite share payload."""

    code: str = Field(..., description="Current user invite code")
    text: str = Field(..., description="Rendered share text with invite code and link")
    link: str = Field(..., description="Invite link URL")
    share_card: InvitationShareCard = Field(..., description="Structured share card payload")


class InvitationIntakeRequest(BaseModel):
    """Invitation intake request for clipboard/link/manual recognition."""

    source: InvitationSource = Field(
        ...,
        description="Event source tag (login/setup/link/invite_bind_page/invite_share_page)",
    )
    trigger: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Trigger tag (e.g. clipboard/link_param/manual_input)",
    )
    raw_text: str | None = Field(default=None, description="Raw clipboard text")
    invite_code: str | None = Field(
        default=None,
        description="Invite code passed by link or manual input",
    )

    @model_validator(mode="after")
    def validate_payload_has_recognition_input(self) -> InvitationIntakeRequest:
        """Ensure at least one recognition input exists."""
        if (self.raw_text is None or self.raw_text.strip() == "") and (
            self.invite_code is None or self.invite_code.strip() == ""
        ):
            raise ValueError("raw_text or invite_code is required")
        return self


class InvitationPublicIntakeResponse(BaseSchema):
    """Public invitation intake response payload."""

    recognized_code: str | None = Field(
        default=None, description="Recognized active invite code or null"
    )
    valid: bool = Field(..., description="Whether recognized_code is active and valid")


class InvitationIntakeResponse(InvitationPublicIntakeResponse):
    """Authenticated invitation intake response payload."""

    bindable: bool = Field(..., description="Whether current user can bind recognized code")


InvitationEventType = Literal[
    "resolve_valid",
    "bind_success",
    "copy_command",
    "share_wechat",
]


class InvitationEventTrackRequest(BaseModel):
    """Invite event tracking payload."""

    event_type: InvitationEventType = Field(..., description="Event type")
    code: str | None = Field(
        default=None, min_length=6, max_length=6, description="Invite code snapshot"
    )
    source: InvitationSource = Field(
        ...,
        description="Event source tag (login/setup/link/invite_bind_page/invite_share_page)",
    )
    payload: dict[str, object] | None = Field(default=None, description="Optional event payload")


class InvitationEventTrackResponse(BaseSchema):
    """Event track acknowledgement."""

    accepted: bool = Field(..., description="Whether event was accepted")
