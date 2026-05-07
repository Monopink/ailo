"""Admin APIs for persona batch submit page."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_admin_session
from app.services.admin.persona_batch_import_store import (
    PersonaBatchImportStoreError,
    PersonaBatchImportTokenForbiddenError,
    PersonaBatchImportTokenNotFoundError,
    consume_persona_batch_import_token,
)
from app.services.ai.persona_batch import (
    PersonaBatchImportRow,
    PersonaBatchSubmitError,
    load_persona_batch_import_rows,
    submit_persona_batch_row,
)

persona_batch_router = APIRouter()


class PersonaBatchSubmitRowResponse(BaseModel):
    """Response payload for a persona batch row submit."""

    status: Literal["success", "failed"]
    local_row_id: str | None = Field(default=None)
    persona_id: str | None = Field(default=None)
    profile_id: str | None = Field(default=None)
    failed_step: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    avatar_url: str | None = Field(default=None)


class PersonaBatchImportRowResponse(BaseModel):
    """Row payload for batch-edit import initialization."""

    persona_id: str
    profile_id: str | None = Field(default=None)
    type_id: int
    type_name: str
    nickname: str | None = Field(default=None)
    gender: int | None = Field(default=None)
    bio: str | None = Field(default=None)
    region: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    remark: str | None = Field(default=None)
    is_reusable: int
    avatar_url: str | None = Field(default=None)


class PersonaBatchImportRowsResponse(BaseModel):
    """Response payload for imported persona rows."""

    items: list[PersonaBatchImportRowResponse]
    imported_count: int


def _require_admin_identity(admin_user: dict[str, Any]) -> tuple[int, str]:
    raw_admin_id = admin_user.get("id")
    raw_username = admin_user.get("username")
    if not isinstance(raw_admin_id, int) or raw_admin_id <= 0:
        raise PersonaBatchSubmitError(step="request_validation", message="Authentication required")
    if not isinstance(raw_username, str) or not raw_username:
        raise PersonaBatchSubmitError(step="request_validation", message="Authentication required")
    return raw_admin_id, raw_username


def _to_import_row_response(row: PersonaBatchImportRow) -> PersonaBatchImportRowResponse:
    return PersonaBatchImportRowResponse(
        persona_id=str(row.persona_id),
        profile_id=str(row.profile_id) if row.profile_id is not None else None,
        type_id=row.type_id,
        type_name=row.type_name,
        nickname=row.nickname,
        gender=row.gender,
        bio=row.bio,
        region=row.region,
        tags=row.tags,
        remark=row.remark,
        is_reusable=row.is_reusable,
        avatar_url=row.avatar_url,
    )


@persona_batch_router.post(
    "/persona-batch/import-rows/consume",
    response_model=PersonaBatchImportRowsResponse,
)
async def consume_persona_batch_rows_endpoint(
    import_token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> PersonaBatchImportRowsResponse:
    """Resolve import token and return selected persona rows."""
    try:
        admin_id, _admin_username = _require_admin_identity(admin_user)
        selection = await consume_persona_batch_import_token(
            admin_id=admin_id,
            token=import_token,
        )
        rows = await load_persona_batch_import_rows(
            db,
            persona_ids=selection.persona_ids,
        )
        return PersonaBatchImportRowsResponse(
            items=[_to_import_row_response(row) for row in rows],
            imported_count=len(rows),
        )
    except PersonaBatchSubmitError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    except PersonaBatchImportTokenNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PersonaBatchImportTokenForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PersonaBatchImportStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@persona_batch_router.post(
    "/persona-batch/submit-row",
    response_model=PersonaBatchSubmitRowResponse,
)
async def submit_persona_batch_row_endpoint(
    local_row_id: str | None = Form(default=None),
    type_id: int = Form(...),
    nickname: str | None = Form(default=None),
    gender: str | None = Form(default=None),
    bio: str | None = Form(default=None),
    region: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    remark: str | None = Form(default=None),
    is_reusable: str | None = Form(default=None),
    persona_id: int | None = Form(default=None),
    profile_id: int | None = Form(default=None),
    avatar_file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> PersonaBatchSubmitRowResponse:
    """Submit a single queue row for persona batch creation/retry."""
    try:
        admin_id, admin_username = _require_admin_identity(admin_user)
        avatar_bytes: bytes | None = None
        avatar_mime_type: str | None = None
        avatar_original_name: str | None = None

        if avatar_file is not None:
            avatar_bytes = await avatar_file.read()
            avatar_mime_type = avatar_file.content_type
            avatar_original_name = avatar_file.filename
            await avatar_file.close()

        result = await submit_persona_batch_row(
            db,
            admin_id=admin_id,
            admin_username=admin_username,
            type_id=type_id,
            nickname=nickname,
            gender=gender,
            bio=bio,
            region=region,
            tags=tags,
            remark=remark,
            is_reusable=is_reusable,
            persona_id=persona_id,
            profile_id=profile_id,
            avatar_file_bytes=avatar_bytes,
            avatar_mime_type=avatar_mime_type,
            avatar_original_name=avatar_original_name,
        )
        return PersonaBatchSubmitRowResponse(
            status="success",
            local_row_id=local_row_id,
            persona_id=str(result.persona_id) if result.persona_id is not None else None,
            profile_id=str(result.profile_id) if result.profile_id is not None else None,
            failed_step=result.failed_step,
            error_message=result.error_message,
            avatar_url=result.avatar_url,
        )
    except PersonaBatchSubmitError as exc:
        return PersonaBatchSubmitRowResponse(
            status="failed",
            local_row_id=local_row_id,
            persona_id=str(exc.persona_id) if exc.persona_id is not None else None,
            profile_id=str(exc.profile_id) if exc.profile_id is not None else None,
            failed_step=exc.step,
            error_message=exc.message,
            avatar_url=None,
        )
