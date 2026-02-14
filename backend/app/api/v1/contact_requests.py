"""Contact request API endpoints.

This module provides endpoints for managing contact requests.
"""

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
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


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
    request_id: int,
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
        result = await accept_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
            accept_data=accept_data,
        )

        logger.info(
            "accept_contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
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
    request_id: int,
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
        result = await ignore_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
        )

        logger.info(
            "ignore_contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
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
