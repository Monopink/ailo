"""
Contact request API endpoints.

This module provides endpoints for managing contact requests.
"""

from typing import Optional

from api.deps import get_current_user
from core.database import get_db
from enums import ContactRequestStatus
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.user import User
from schemas.contact import (
    ContactRequestAccept,
    ContactRequestCreate,
    ContactRequestListResponse,
    ContactResponse,
)
from services.contact import (
    accept_contact_request_service,
    create_contact_request_service,
    get_contact_requests_service,
    reject_contact_request_service,
)
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=dict)
async def create_contact_request(
    request: ContactRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send contact request.

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
            detail="系统错误，请稍后再试",
        )


@router.get("", response_model=ContactRequestListResponse)
async def get_contact_requests(
    status_filter: Optional[ContactRequestStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's received contact requests.

    Returns a list of contact requests with applicant profile information.

    **Query Parameters:**
    - status: Filter by request status (1=pending, 2=accepted, 3=ignored, 4=expired, 5=rejected)
    - cursor: Pagination cursor (not implemented yet)
    - limit: Number of items to return (1-100, default 20)

    **Error Codes:**
    - 500: System error
    """
    try:
        result = await get_contact_requests_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            status_filter=status_filter,
            cursor=cursor,
            limit=limit,
        )

        logger.info(
            "get_contact_requests_api_success",
            user_qiao_id=current_user.qiao_id,
            status=status_filter,
            count=len(result.items),
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_contact_requests_api_failed",
            user_qiao_id=current_user.qiao_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取请求列表失败",
        )


@router.post("/{request_id}/accept", response_model=ContactResponse)
async def accept_contact_request(
    request_id: int,
    accept_data: ContactRequestAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a contact request.

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
            detail="接受请求失败",
        )


@router.post("/{request_id}/reject", response_model=dict)
async def reject_contact_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a contact request.

    Updates the request status to rejected. Does not send notification to the applicant.

    **Path Parameters:**
    - request_id: Contact request ID

    **Error Codes:**
    - 400: Invalid request status
    - 403: Not authorized to reject this request
    - 404: Request not found
    - 500: System error
    """
    try:
        result = await reject_contact_request_service(
            db=db,
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
        )

        logger.info(
            "reject_contact_request_api_success",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "reject_contact_request_api_failed",
            user_qiao_id=current_user.qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="拒绝请求失败",
        )
