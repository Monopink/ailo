"""Admin persona batch submit orchestration service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AIPersonaStatus, Gender, ProfileOwnerType, ReusableStatus, UploaderType
from app.models.ai.template import AIPersona, AIType
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.services.media.uploader import UploadActor
from app.services.profile.admin_avatar import upload_admin_avatar_for_profile
from app.services.profile.avatar import get_avatar_url
from app.services.profile.integrity import ensure_persona_profile
from app.type_defs import JSONValue
from app.utils.contact_tags import (
    TAG_MAX_COUNT,
    TAG_MAX_LENGTH,
    TAG_MAX_TOTAL_LENGTH,
    compute_total_length,
    normalize_tags,
)
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_REMARK_RULE, validate_text_limit

logger = get_logger(__name__)

_QIAO_ID_RETRY_LIMIT = 5
_NICKNAME_MAX_LENGTH = 100
_REGION_MAX_LENGTH = 100


@dataclass
class PersonaBatchSubmitResult:
    """Single-row submit result for admin persona batch workflow."""

    status: str
    persona_id: int | None
    profile_id: int | None
    failed_step: str | None
    error_message: str | None
    avatar_url: str | None


@dataclass
class PersonaBatchImportRow:
    """Persona row payload used by batch-edit import."""

    persona_id: int
    profile_id: int | None
    type_id: int
    type_name: str
    nickname: str | None
    gender: int | None
    bio: str | None
    region: str | None
    tags: list[str]
    remark: str | None
    is_reusable: int
    avatar_url: str | None


class PersonaBatchSubmitError(RuntimeError):
    """Domain error for persona batch row submission."""

    def __init__(
        self,
        *,
        step: str,
        message: str,
        persona_id: int | None = None,
        profile_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.step = step
        self.message = message
        self.persona_id = persona_id
        self.profile_id = profile_id


async def submit_persona_batch_row(
    db: AsyncSession,
    *,
    admin_id: int,
    admin_username: str,
    type_id: int,
    nickname: str | None,
    gender: str | None,
    bio: str | None,
    region: str | None,
    tags: str | None,
    remark: str | None,
    is_reusable: str | None,
    persona_id: int | None,
    profile_id: int | None,
    avatar_file_bytes: bytes | None,
    avatar_mime_type: str | None,
    avatar_original_name: str | None,
) -> PersonaBatchSubmitResult:
    """Create or retry a persona row and update profile nickname/avatar."""
    persona: AIPersona | None = None
    profile: Profile | None = None
    try:
        await _ensure_ai_type_exists(db, type_id=type_id)
        persona, profile = await _prepare_persona_and_profile(
            db,
            type_id=type_id,
            persona_id=persona_id,
            profile_id=profile_id,
        )

        normalized_nickname = _normalize_nickname(nickname)
        normalized_gender = _normalize_gender(gender)
        normalized_bio = _normalize_bio(bio)
        normalized_region = _normalize_region(region)
        normalized_tags = _normalize_tags_input(tags)
        normalized_remark = _normalize_remark(remark)
        normalized_is_reusable = _normalize_is_reusable(is_reusable)

        persona.tags = cast(JSONValue | None, normalized_tags)
        persona.remark = normalized_remark
        persona.is_reusable = normalized_is_reusable
        profile.nickname = normalized_nickname
        profile.gender = normalized_gender
        profile.bio = normalized_bio
        profile.region = normalized_region
        await db.commit()
        await db.refresh(profile)

        if avatar_file_bytes:
            profile = await _upload_avatar(
                db,
                profile=profile,
                admin_id=admin_id,
                admin_username=admin_username,
                file_bytes=avatar_file_bytes,
                mime_type=avatar_mime_type or "application/octet-stream",
                original_name=avatar_original_name,
            )

        avatar_url = await get_avatar_url(profile)
        return PersonaBatchSubmitResult(
            status="success",
            persona_id=persona.id,
            profile_id=profile.id,
            failed_step=None,
            error_message=None,
            avatar_url=avatar_url,
        )
    except PersonaBatchSubmitError:
        await _safe_rollback(db)
        raise
    except HTTPException as exc:
        await _safe_rollback(db)
        raise PersonaBatchSubmitError(
            step="request_validation",
            message=str(exc.detail),
            persona_id=persona.id if persona is not None else persona_id,
            profile_id=profile.id if profile is not None else profile_id,
        ) from exc
    except Exception as exc:
        await _safe_rollback(db)
        logger.exception("admin_persona_batch_submit_row_failed")
        raise PersonaBatchSubmitError(
            step="unknown",
            message="Unexpected server error",
            persona_id=persona.id if persona is not None else persona_id,
            profile_id=profile.id if profile is not None else profile_id,
        ) from exc


async def load_persona_batch_import_rows(
    db: AsyncSession,
    *,
    persona_ids: list[int],
) -> list[PersonaBatchImportRow]:
    """Load persona+profile rows for batch-edit import."""
    normalized_ids = _normalize_persona_ids(persona_ids)
    if not normalized_ids:
        return []

    stmt = (
        select(AIPersona, AIType.display_name, Profile)
        .outerjoin(AIType, AIType.id == AIPersona.type_id)
        .outerjoin(
            Profile,
            and_(
                Profile.owner_id == AIPersona.id,
                Profile.owner_type == int(ProfileOwnerType.AI_PERSONA),
            ),
        )
        .where(AIPersona.id.in_(normalized_ids))
    )
    result = await db.execute(stmt)
    by_persona_id: dict[int, PersonaBatchImportRow] = {}
    for persona, type_display_name, profile in result.all():
        type_name = (
            str(type_display_name).strip()
            if isinstance(type_display_name, str) and type_display_name.strip()
            else f"Type {persona.type_id}"
        )
        tags = _to_tag_list(persona.tags)
        avatar_url = await get_avatar_url(profile)
        by_persona_id[persona.id] = PersonaBatchImportRow(
            persona_id=persona.id,
            profile_id=profile.id if profile is not None else None,
            type_id=persona.type_id,
            type_name=type_name,
            nickname=profile.nickname if profile is not None else None,
            gender=profile.gender if profile is not None else None,
            bio=profile.bio if profile is not None else None,
            region=profile.region if profile is not None else None,
            tags=tags,
            remark=persona.remark,
            is_reusable=int(persona.is_reusable),
            avatar_url=avatar_url,
        )

    ordered_rows: list[PersonaBatchImportRow] = []
    for persona_id in normalized_ids:
        row = by_persona_id.get(persona_id)
        if row is not None:
            ordered_rows.append(row)
    return ordered_rows


async def _ensure_ai_type_exists(db: AsyncSession, *, type_id: int) -> None:
    result = await db.execute(select(AIType.id).where(AIType.id == type_id))
    if result.scalar_one_or_none() is None:
        raise PersonaBatchSubmitError(step="create_persona", message="AI type not found")


async def _prepare_persona_and_profile(
    db: AsyncSession,
    *,
    type_id: int,
    persona_id: int | None,
    profile_id: int | None,
) -> tuple[AIPersona, Profile]:
    if persona_id is None:
        persona = await _create_persona(db, type_id=type_id)
    else:
        persona = await _load_persona(db, persona_id=persona_id)
        if persona.type_id != type_id:
            raise PersonaBatchSubmitError(
                step="create_persona",
                message="Type mismatch with existing persona",
                persona_id=persona.id,
            )

    if profile_id is not None:
        profile = await _load_profile_for_persona(
            db,
            profile_id=profile_id,
            persona_id=persona.id,
            persona_qiao_id=persona.qiao_id,
        )
    else:
        profile = await _ensure_profile_for_persona(db, persona=persona)

    return persona, profile


async def _create_persona(db: AsyncSession, *, type_id: int) -> AIPersona:
    for _attempt in range(_QIAO_ID_RETRY_LIMIT):
        persona = AIPersona(
            type_id=type_id,
            qiao_id=generate_qiao_id(),
            username=None,
            tags=None,
            remark=None,
            is_reusable=int(ReusableStatus.REUSABLE),
            status=int(AIPersonaStatus.ACTIVE),
        )
        db.add(persona)
        try:
            await db.flush()
            return persona
        except IntegrityError:
            await db.rollback()
            continue
    raise PersonaBatchSubmitError(
        step="create_persona",
        message="Failed to allocate unique persona qiao_id after retries",
    )


async def _load_persona(db: AsyncSession, *, persona_id: int) -> AIPersona:
    persona = await db.get(AIPersona, persona_id)
    if persona is None:
        raise PersonaBatchSubmitError(step="create_persona", message="Persona not found")
    return persona


async def _ensure_profile_for_persona(db: AsyncSession, *, persona: AIPersona) -> Profile:
    try:
        return await ensure_persona_profile(
            db,
            persona_id=persona.id,
            persona_qiao_id=persona.qiao_id,
            source="admin_persona_batch_submit",
            commit=False,
        )
    except Exception as exc:
        raise PersonaBatchSubmitError(
            step="ensure_profile",
            message="Failed to ensure persona profile",
            persona_id=persona.id,
        ) from exc


async def _load_profile_for_persona(
    db: AsyncSession,
    *,
    profile_id: int,
    persona_id: int,
    persona_qiao_id: str,
) -> Profile:
    profile = await db.get(Profile, profile_id)
    if profile is None:
        raise PersonaBatchSubmitError(
            step="ensure_profile",
            message="Profile not found",
            persona_id=persona_id,
            profile_id=profile_id,
        )
    if int(profile.owner_id) != persona_id or profile.owner_qiao_id != persona_qiao_id:
        raise PersonaBatchSubmitError(
            step="ensure_profile",
            message="Profile does not belong to persona",
            persona_id=persona_id,
            profile_id=profile_id,
        )
    return profile


async def _upload_avatar(
    db: AsyncSession,
    *,
    profile: Profile,
    admin_id: int,
    admin_username: str,
    file_bytes: bytes,
    mime_type: str,
    original_name: str | None,
) -> Profile:
    actor = UploadActor(
        uploader_type=UploaderType.ADMIN,
        uploader_id=admin_id,
        uploader_qiao_id=admin_username,
        rate_limit_subject=f"admin:{admin_id}",
        confirmed_by_id=admin_id,
    )
    try:
        updated_profile, _deduplicated = await upload_admin_avatar_for_profile(
            db,
            profile=profile,
            actor=actor,
            file_bytes=file_bytes,
            mime_type=mime_type,
            file_size=len(file_bytes),
            original_name=original_name,
            crop=None,
        )
        return updated_profile
    except Exception as exc:
        raise PersonaBatchSubmitError(
            step="upload_avatar",
            message="Avatar upload failed",
            persona_id=int(profile.owner_id),
            profile_id=profile.id,
        ) from exc


def _normalize_nickname(nickname: str | None) -> str | None:
    if nickname is None:
        return None
    stripped = nickname.strip()
    if not stripped:
        return None
    if len(stripped) > _NICKNAME_MAX_LENGTH:
        raise PersonaBatchSubmitError(
            step="update_nickname",
            message=f"Nickname length must be <= {_NICKNAME_MAX_LENGTH}",
        )
    return stripped


def _normalize_gender(gender: str | None) -> int | None:
    if gender is None:
        return None
    stripped = gender.strip()
    if not stripped:
        return None
    try:
        value = int(stripped)
    except (TypeError, ValueError) as exc:
        raise PersonaBatchSubmitError(
            step="update_gender",
            message="Gender must be one of 1, 2, 3",
        ) from exc
    allowed_values = {int(Gender.MALE), int(Gender.FEMALE), int(Gender.OTHER)}
    if value not in allowed_values:
        raise PersonaBatchSubmitError(
            step="update_gender",
            message="Gender must be one of 1, 2, 3",
        )
    return value


def _normalize_persona_ids(persona_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for raw_id in persona_ids:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _to_tag_list(raw_tags: object) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    return [str(item).strip() for item in raw_tags if isinstance(item, str) and item.strip()]


def _normalize_bio(bio: str | None) -> str | None:
    if bio is None:
        return None
    stripped = bio.strip()
    if not stripped:
        return None
    return stripped


def _normalize_region(region: str | None) -> str | None:
    if region is None:
        return None
    stripped = region.strip()
    if not stripped:
        return None
    if len(stripped) > _REGION_MAX_LENGTH:
        raise PersonaBatchSubmitError(
            step="update_region",
            message=f"Region length must be <= {_REGION_MAX_LENGTH}",
        )
    return stripped


def _normalize_tags_input(tags: str | None) -> list[str] | None:
    if tags is None:
        return None
    stripped = tags.strip()
    if not stripped:
        return None

    parsed_items: list[str]
    if stripped.startswith("["):
        try:
            decoded = json.loads(stripped)
        except Exception as exc:
            raise PersonaBatchSubmitError(
                step="update_tags",
                message="Tags must be a JSON array or comma-separated string",
            ) from exc
        if not isinstance(decoded, list) or any(not isinstance(item, str) for item in decoded):
            raise PersonaBatchSubmitError(
                step="update_tags",
                message="Tags JSON must be an array of strings",
            )
        parsed_items = decoded
    else:
        parsed_items = [item.strip() for item in stripped.split(",")]

    normalized = normalize_tags(parsed_items) or []
    if not normalized:
        return None
    if any(len(tag) > TAG_MAX_LENGTH for tag in normalized):
        raise PersonaBatchSubmitError(
            step="update_tags",
            message=f"Each tag must be at most {TAG_MAX_LENGTH} characters",
        )
    if len(normalized) > TAG_MAX_COUNT:
        raise PersonaBatchSubmitError(
            step="update_tags",
            message=f"Tag count must be at most {TAG_MAX_COUNT}",
        )
    if compute_total_length(normalized) > TAG_MAX_TOTAL_LENGTH:
        raise PersonaBatchSubmitError(
            step="update_tags",
            message=f"Total tags length must be at most {TAG_MAX_TOTAL_LENGTH}",
        )
    return normalized


def _normalize_remark(remark: str | None) -> str | None:
    if remark is None:
        return None
    stripped = remark.strip()
    if not stripped:
        return None
    remark_error = validate_text_limit(stripped, CONTACT_REMARK_RULE)
    if remark_error is not None:
        raise PersonaBatchSubmitError(
            step="update_remark",
            message=remark_error,
        )
    return stripped


def _normalize_is_reusable(is_reusable: str | None) -> int:
    if is_reusable is None or not is_reusable.strip():
        return int(ReusableStatus.REUSABLE)
    stripped = is_reusable.strip()
    if stripped not in {"0", "1"}:
        raise PersonaBatchSubmitError(
            step="update_is_reusable",
            message="is_reusable must be 0 or 1",
        )
    return int(stripped)


async def _safe_rollback(db: AsyncSession) -> None:
    if db.in_transaction():
        await db.rollback()
