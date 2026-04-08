"""Custom view for profile avatar advanced editing."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import CustomView

from app.core.database import get_sessionmaker
from app.enums import ProfileOwnerType
from app.models.profile import Profile
from app.services.profile.avatar import get_avatar_url


class ProfileAvatarAdvancedEditView(CustomView):
    """Render profile avatar advanced edit page."""

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        try:
            profile_id = int(request.path_params["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid profile ID") from exc

        session_factory = get_sessionmaker()
        async with session_factory() as db:
            result = await db.execute(select(Profile).where(Profile.id == profile_id))
            profile = result.scalar_one_or_none()
            if profile is None:
                raise HTTPException(status_code=404, detail="Profile not found")
            avatar_url = await get_avatar_url(profile)

        context = {
            "request": request,
            "profile": {
                "id": str(profile.id),
                "owner_qiao_id": profile.owner_qiao_id,
                "owner_type": profile.owner_type,
                "owner_type_display": _owner_type_label(profile.owner_type),
                "nickname": profile.nickname,
                "avatar_url": avatar_url,
                "avatar_media_id": (
                    str(profile.avatar_media_id) if profile.avatar_media_id is not None else None
                ),
            },
        }
        return templates.TemplateResponse("custom_views/profile_avatar_advanced_edit.html", context)


profile_avatar_advanced_edit_view = ProfileAvatarAdvancedEditView(
    label="Profile Avatar Advanced Edit",
    name="profile_avatar_advanced_edit",
    path="/profile/advanced-edit/{id:int}",
    add_to_menu=False,
)


def _owner_type_label(owner_type: int) -> str:
    if owner_type == int(ProfileOwnerType.USER):
        return "User"
    if owner_type == int(ProfileOwnerType.AI_PERSONA):
        return "AI Persona"
    if owner_type == int(ProfileOwnerType.AI_INSTANCE):
        return "AI Instance"
    return str(owner_type)
