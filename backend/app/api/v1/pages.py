"""Public app page APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.app_page import AppPageListResponse, AppPageResponse
from app.services.pages import service as app_page_service
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/pages", tags=["Pages"])


def _require_client_header(request: Request) -> str:
    client = (request.headers.get("X-Client", "") or "").strip()
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 X-Client header")
    return client


@router.get("", response_model=AppPageListResponse)
async def get_pages(
    request: Request,
    page_keys: str = Query(..., description="Comma separated page keys"),
    db: AsyncSession = Depends(get_db),
) -> AppPageListResponse:
    """Get app pages by page keys."""
    client_type = _require_client_header(request)
    try:
        items = await app_page_service.get_pages(
            db,
            client_type=client_type,
            raw_page_keys=page_keys,
        )
        return AppPageListResponse(items=items)
    except app_page_service.AppPageValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    except app_page_service.AppPageNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请求不存在")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "get_pages_error",
            client_type=client_type,
            page_keys=page_keys,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")


@router.get("/{page_key}", response_model=AppPageResponse)
async def get_page(
    page_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AppPageResponse:
    """Get one app page by page key."""
    client_type = _require_client_header(request)
    try:
        return await app_page_service.get_page(
            db,
            client_type=client_type,
            page_key=page_key,
        )
    except app_page_service.AppPageValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    except app_page_service.AppPageNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请求不存在")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "get_page_error",
            client_type=client_type,
            page_key=page_key,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="系统错误")
