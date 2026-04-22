"""Invitation share card resolver based on operation slot config."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.invite import operation_slot_config as operation_slot_config_crud

INVITE_SHARE_SLOT_CODE = "invite_share_card"
INVITE_SHARE_CHANNEL = "mini_program"
INVITE_SHARE_PATH_CODE_PLACEHOLDER = "{{code}}"


@dataclass(frozen=True)
class InviteShareCardPayload:
    """Resolved invite share card payload."""

    title: str
    path: str
    image_url: str
    slot_code: str
    channel: str
    version: int


def _render_path_template(path_template: str, code: str) -> str:
    """Render path template with invite code placeholder."""
    if path_template.count(INVITE_SHARE_PATH_CODE_PLACEHOLDER) != 1:
        raise ValueError("invalid_path_template")
    return path_template.replace(INVITE_SHARE_PATH_CODE_PLACEHOLDER, code)


async def resolve_invite_share_card(
    db: AsyncSession,
    *,
    code: str,
    now: datetime | None = None,
) -> InviteShareCardPayload | None:
    """Resolve active invite share card payload from operation slot config."""
    resolved = await operation_slot_config_crud.get_one_active_slot_with_asset(
        db,
        slot_code=INVITE_SHARE_SLOT_CODE,
        channel=INVITE_SHARE_CHANNEL,
        now=now or datetime.now(UTC),
    )
    if resolved is None:
        return None

    slot, asset = resolved
    return InviteShareCardPayload(
        title=slot.title,
        path=_render_path_template(slot.path_template, code),
        image_url=asset.cdn_url,
        slot_code=slot.slot_code,
        channel=slot.channel,
        version=int(slot.version),
    )
