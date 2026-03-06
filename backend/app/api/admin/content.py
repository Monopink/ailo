"""Admin APIs for content editing utilities."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.deps import get_db, verify_admin_session
from app.enums import AdminOperationType
from app.models.content import AppPage
from app.services.pages import service as app_page_service
from app.utils.admin_logs import create_operation_log
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AppPageRenderRequest(BaseModel):
    """Payload for markdown rendering preview."""

    content_md: str = Field(..., description="Markdown source content")


class AppPageSaveRequest(BaseModel):
    """Payload for saving app page through advanced edit page."""

    title: str = Field("", max_length=200)
    content_md: str = Field("")
    content_html: str = Field("")


async def _get_app_page_or_404(db: AsyncSession, page_id: int) -> AppPage:
    document = await db.get(AppPage, page_id)
    if document is None:
        raise HTTPException(status_code=404, detail="App page not found")
    return document


@router.post("/app-page/{page_id}/render")
async def render_app_page_markdown(
    page_id: int,
    payload: AppPageRenderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Render markdown content for admin preview without saving."""
    await _get_app_page_or_404(db, page_id)

    try:
        content_rendered = app_page_service.render_markdown_to_html(payload.content_md)
    except app_page_service.AppPageValidationError as exc:
        raise HTTPException(status_code=400, detail="Invalid markdown content") from exc

    return {
        "content_rendered_format": app_page_service.CONTENT_RENDERED_FORMAT_HTML,
        "content_rendered": content_rendered,
    }


@router.post("/app-page/{page_id}/save")
async def save_app_page_advanced(
    page_id: int,
    payload: AppPageSaveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: dict[str, Any] = Depends(verify_admin_session),
) -> dict[str, str | int]:
    """Save mutable app page fields from advanced editing page."""
    page = await _get_app_page_or_404(db, page_id)

    title = payload.title.strip()

    try:
        source_type = app_page_service.normalize_source_type(page.source_type)
        content_md, content_html = app_page_service.resolve_page_contents(
            source_type=source_type,
            content_md=payload.content_md,
            content_html=payload.content_html,
        )
    except app_page_service.AppPageValidationError as exc:
        raise HTTPException(status_code=400, detail="Invalid app page content") from exc

    page.title = title
    page.content_md = content_md
    page.content_html = content_html

    await db.commit()
    await db.refresh(page)

    raw_admin_user_id = admin_user.get("id")
    admin_user_id: int | None = None
    if isinstance(raw_admin_user_id, int):
        admin_user_id = raw_admin_user_id
    elif isinstance(raw_admin_user_id, str):
        try:
            admin_user_id = int(raw_admin_user_id)
        except ValueError:
            admin_user_id = None

    if admin_user_id is not None:
        await create_operation_log(
            db=db,
            admin_user_id=admin_user_id,
            operation_type=AdminOperationType.UPDATE.value,
            resource_type="app_page",
            resource_id=str(page.id),
            resource_name=page.page_key,
            operation_desc="Updated app page via advanced editor",
            request=request,
        )
    else:
        logger.warning(
            "app_page_advanced_save_missing_admin_user_id",
            page_id=page_id,
        )

    return {
        "id": page.id,
        "content_rendered_format": app_page_service.CONTENT_RENDERED_FORMAT_HTML,
        "content_rendered": str(page.content_html or ""),
    }
