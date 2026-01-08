"""Contact management API endpoints.

This module provides endpoints for managing user contacts and conversations.
"""

import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.contact import (
    ContactDetailResponse,
    ContactListPagination,
    ContactListResult,
    ContactUpdate,
    ConversationInfoResponse,
)
from app.services.contact import (
    block_contact,
    delete_contact,
    get_contact_with_profile,
    get_conversation_info,
    get_user_contacts_with_profiles,
    unblock_contact,
    update_contact,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/contacts", tags=["Contacts"])


def _decode_cursor(cursor: str | None) -> int:
    """Decode opaque cursor into skip offset."""
    if not cursor:
        return 0

    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + padding).encode()).decode()
        return max(int(decoded), 0)
    except Exception:
        return 0


def _encode_cursor(offset: int) -> str:
    """Encode skip offset into opaque cursor."""
    return base64.urlsafe_b64encode(str(offset).encode()).decode().rstrip("=")


@router.get("", response_model=ContactListResult)
async def get_contacts(
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactListResult:
    """Get user's contact list.

    Returns a paginated list of contacts with presentation information.

    Args:
        cursor: Pagination cursor
        limit: Maximum number of contacts to return (1-100)
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated contact list

    Raises:
        HTTPException: 500 if retrieval fails

    """
    try:
        skip = _decode_cursor(cursor)

        contacts, has_more = await get_user_contacts_with_profiles(
            db=db,
            user_qiao_id=current_user.qiao_id,
            skip=skip,
            limit=limit,
        )

        next_cursor = _encode_cursor(skip + len(contacts)) if has_more else None

        logger.info(
            "contacts_list_retrieved",
            user_qiao_id=current_user.qiao_id,
            count=len(contacts),
        )

        return ContactListResult(
            items=contacts,
            pagination=ContactListPagination(cursor=next_cursor, has_more=has_more),
        )

    except ValueError as e:
        # Configuration error (e.g., IM conv_id not configured)
        logger.error(
            "contacts_list_config_error",
            user_qiao_id=current_user.qiao_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "contacts_list_failed",
            user_qiao_id=current_user.qiao_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.get("/{conv_id}", response_model=ContactDetailResponse)
async def get_contact(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Get specific contact details.

    Returns detailed information about a specific contact.

    Args:
        conv_id: Conversation identifier
        current_user: Authenticated user
        db: Database session

    Returns:
        ContactDetailResponse

    Raises:
        HTTPException: 404 if contact not found, 500 for internal errors

    """
    try:
        contact = await get_contact_with_profile(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="操作异常",
            )

        logger.info(
            "contact_detail_retrieved",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_detail_config_error",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "contact_detail_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.get("/{conv_id}/conversation", response_model=ConversationInfoResponse)
async def get_contact_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationInfoResponse:
    """Get conversation information.

    Returns conversation information including contact basic info and IM conversation ID.
    Used by messaging client to initialize conversation.

    Args:
        conv_id: Conversation identifier
        current_user: Authenticated user
        db: Database session

    Returns:
        ConversationInfoResponse with im_conv_id and contact info

    Raises:
        HTTPException: 404 if conversation not found, 500 for internal errors

    """
    try:
        conversation = await get_conversation_info(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="操作异常",
            )

        logger.info(
            "conversation_info_retrieved",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return conversation

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "conversation_info_config_error",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "conversation_info_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.put("/{conv_id}", response_model=ContactDetailResponse)
async def update_contact_info(
    conv_id: str,
    update_data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Update contact information.

    Allows updating contact alias, tags, remark, pin status, mute status, and block status.
    All fields are optional - only provided fields will be updated.

    Args:
        conv_id: Conversation identifier
        update_data: Contact update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated contact information

    Raises:
        HTTPException: 400 if contact not found or access denied
        HTTPException: 500 if update fails

    """
    try:
        updated_contact = await update_contact(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            update_data=update_data,
        )

        if not updated_contact:
            logger.warning(
                "contact_update_not_found",
                user_qiao_id=current_user.qiao_id,
                conv_id=conv_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_updated_via_api",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return updated_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_update_config_error",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "contact_update_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.post("/{conv_id}/block", response_model=ContactDetailResponse)
async def block_contact_endpoint(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Block a contact.

    Blocks the specified contact, preventing messages from being received.

    Args:
        conv_id: Conversation identifier
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated contact information with is_blocked=True

    Raises:
        HTTPException: 400 if contact not found or access denied
        HTTPException: 500 if block operation fails

    """
    try:
        blocked_contact = await block_contact(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        if not blocked_contact:
            logger.warning(
                "contact_block_not_found",
                user_qiao_id=current_user.qiao_id,
                conv_id=conv_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_blocked_via_api",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return blocked_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_block_config_error",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "contact_block_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.post("/{conv_id}/unblock", response_model=ContactDetailResponse)
async def unblock_contact_endpoint(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Unblock a contact.

    Unblocks the specified contact, allowing messages to be received again.

    Args:
        conv_id: Conversation identifier
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated contact information with is_blocked=False

    Raises:
        HTTPException: 400 if contact not found or access denied
        HTTPException: 500 if unblock operation fails

    """
    try:
        unblocked_contact = await unblock_contact(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        if not unblocked_contact:
            logger.warning(
                "contact_unblock_not_found",
                user_qiao_id=current_user.qiao_id,
                conv_id=conv_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_unblocked_via_api",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return unblocked_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_unblock_config_error",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
    except Exception as e:
        logger.error(
            "contact_unblock_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_endpoint(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a contact.

    Soft deletes the contact relationship. Chat history is not deleted (managed by client).

    Args:
        conv_id: Conversation identifier
        current_user: Current authenticated user
        db: Database session

    Returns:
        No content (204)

    Raises:
        HTTPException: 400 if contact not found or access denied
        HTTPException: 500 if delete operation fails

    """
    try:
        success = await delete_contact(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        if not success:
            logger.warning(
                "contact_delete_not_found",
                user_qiao_id=current_user.qiao_id,
                conv_id=conv_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_deleted_via_api",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
        )

        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "contact_delete_failed",
            user_qiao_id=current_user.qiao_id,
            conv_id=conv_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后再试",
        )
