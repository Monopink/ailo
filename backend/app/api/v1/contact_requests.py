"""Contact request API endpoints.

This module provides endpoints for managing contact requests.
"""

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.contact import ContactDetailResponse, ContactRequestAccept, ContactRequestCreate
from app.services.contact import (
    accept_contact_request_service,
    create_contact_request_service,
    ignore_contact_request_service,
)
from app.utils.contact_tags import normalize_tags, validate_tags
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_ALIAS_RULE, validate_text_limit

logger = get_logger(__name__)

router = APIRouter()

_CONTACT_REQUEST_ID_PATTERN = re.compile(r"^[0-9]+$")


def _parse_contact_request_id_or_raise(raw_request_id: str) -> int:
    """Parse contact request Snowflake ID from path parameter."""
    candidate = raw_request_id.strip()
    if not candidate or not _CONTACT_REQUEST_ID_PATTERN.fullmatch(candidate):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    request_id = int(candidate)
    if request_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求参数错误")
    return request_id


def _validate_contact_alias_or_raise(alias: str | None) -> None:
    """Validate contact alias text limit for request flows."""
    if alias is None:
        return

    alias_error = validate_text_limit(alias, CONTACT_ALIAS_RULE)
    if alias_error is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=alias_error,
        )


@router.post("", response_model=dict)
async def create_contact_request(
    request: ContactRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send contact request.

    Unified API for adding both AI and user contacts.
    Backend automatically routes to appropriate handler based on target type.

    **Error Codes:**
    - 400: Validation failed (already added, limit exceeded, etc.)
    - 500: System error
    """
    try:
        _validate_contact_alias_or_raise(request.alias)
        normalized_tags = normalize_tags(request.tags)
        if normalized_tags is not None:
            tag_error = validate_tags(normalized_tags)
            if tag_error is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=tag_error)
            request = request.model_copy(update={"tags": normalized_tags})

        result = await create_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request=request,
        )

        logger.info(
            "contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            to_qiao_id=request.to_qiao_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "contact_request_api_failed",
            user_qiao_id=current_user.qiao_id,
            to_qiao_id=request.to_qiao_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.post("/{request_id}/accept", response_model=ContactDetailResponse)
async def accept_contact_request(
    request_id: str,
    accept_data: ContactRequestAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Accept a contact request.

    Creates a contact relationship and sends notification to the applicant.

    **Path Parameters:**
    - request_id: Contact request ID

    **Request Body:**
    - alias: Optional contact alias/remark name
    - tags: Optional contact tags

    **Error Codes:**
    - 400: Invalid request status or contact already exists
    - 403: Not authorized to accept this request
    - 404: Request not found
    - 500: System error
    """
    try:
        parsed_request_id = _parse_contact_request_id_or_raise(request_id)
        _validate_contact_alias_or_raise(accept_data.alias)
        normalized_tags = normalize_tags(accept_data.tags)
        if normalized_tags is not None:
            tag_error = validate_tags(normalized_tags)
            if tag_error is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=tag_error)
            accept_data = accept_data.model_copy(update={"tags": normalized_tags})

        result = await accept_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request_id=parsed_request_id,
            accept_data=accept_data,
        )

        logger.info(
            "accept_contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            request_id=parsed_request_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "accept_contact_request_api_failed",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.post("/{request_id}/ignore", response_model=dict)
async def ignore_contact_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ignore a contact request.

    Updates the request status to ignored. Does not send notification to the applicant.

    **Path Parameters:**
    - request_id: Contact request ID

    **Error Codes:**
    - 400: Invalid request status
    - 403: Not authorized to ignore this request
    - 404: Request not found
    - 500: System error
    """
    try:
        parsed_request_id = _parse_contact_request_id_or_raise(request_id)
        result = await ignore_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request_id=parsed_request_id,
        )

        logger.info(
            "ignore_contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            request_id=parsed_request_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "ignore_contact_request_api_failed",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
