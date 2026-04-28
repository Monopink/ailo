"""Invitation share card resolver based on fixed path + media base URL."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.media.config import get_media_base_url

INVITE_SHARE_PATH_CODE_PLACEHOLDER = "{{code}}"
INVITE_SHARE_QUERY_PARAM = "inviteCode"
INVITE_SHARE_PAGE_PATH = "/pages/boot/boot"
INVITE_SHARE_PATH_TEMPLATE = (
    f"{INVITE_SHARE_PAGE_PATH}?{INVITE_SHARE_QUERY_PARAM}={INVITE_SHARE_PATH_CODE_PLACEHOLDER}"
)
INVITE_SHARE_CARD_IMAGE_OBJECT_KEY = "share/invite-share-card.webp"


@dataclass(frozen=True)
class InviteShareCardPayload:
    """Resolved invite share card payload."""

    path: str
    image_url: str


def _render_path(code: str) -> str:
    """Render fixed invite-share path with invite code placeholder."""
    return INVITE_SHARE_PATH_TEMPLATE.replace(INVITE_SHARE_PATH_CODE_PLACEHOLDER, code)


def _build_image_url() -> str:
    """Build invite share card image URL from configured media base URL."""
    return f"{get_media_base_url()}/{INVITE_SHARE_CARD_IMAGE_OBJECT_KEY}"


def resolve_invite_share_card(*, code: str) -> InviteShareCardPayload:
    """Resolve invite share card payload from fixed constants."""
    return InviteShareCardPayload(
        path=_render_path(code),
        image_url=_build_image_url(),
    )
