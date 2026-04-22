"""Contact management API endpoints.

This module provides endpoints for managing user contacts and conversations.
"""

import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.contact import contact as contact_crud
from app.enums import ContactType
from app.models.user import User
from app.schemas.contact import (
    ContactDetailResponse,
    ContactLimitResponse,
    ContactListPagination,
    ContactListResult,
    ContactUpdate,
)
from app.services.contact import (
    block_contact,
    delete_contact,
    get_contact_with_profile,
    get_user_contacts_with_profiles,
    unblock_contact,
    update_contact,
)
from app.services.entitlement.service import get_ai_contact_limit as get_ai_contact_limit_by_user_id
from app.utils.contact_tags import normalize_tags, validate_tags
from app.utils.logging import get_logger
from app.utils.text_limits import CONTACT_ALIAS_RULE, CONTACT_REMARK_RULE, validate_text_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/contacts", tags=["Contacts"])

CONTACTS_LIMIT_MIN = 1
CONTACTS_LIMIT_MAX = 100


@router.get("/limit", response_model=ContactLimitResponse)
async def get_contact_limit_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactLimitResponse:
    """Get contact usage and available slot count for current user."""
    try:
        available_total = await get_ai_contact_limit_by_user_id(db, user_id=current_user.id)
        used = await contact_crud.count_user_contacts(
            db,
            user_qiao_id=current_user.qiao_id,
            contact_type=ContactType.AI,
        )
        return ContactLimitResponse(used=used, available_total=available_total)
    except Exception as exc:
        logger.error(
            "contacts_ai_limit_failed",
            user_qiao_id=current_user.qiao_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


def _normalize_and_validate_contact_update_payload_or_raise(
    update_data: ContactUpdate,
) -> ContactUpdate:
    """Validate and normalize user-editable contact fields."""
    provided_fields = update_data.model_fields_set

    if "alias" in provided_fields and update_data.alias is not None:
        alias_error = validate_text_limit(update_data.alias, CONTACT_ALIAS_RULE)
        if alias_error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=alias_error,
            )

    if "remark" in provided_fields and update_data.remark is not None:
        remark_error = validate_text_limit(update_data.remark, CONTACT_REMARK_RULE)
        if remark_error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=remark_error,
            )

    if "tags" in provided_fields and update_data.tags is not None:
        normalized_tags = normalize_tags(update_data.tags) or []
        tag_error = validate_tags(normalized_tags)
        if tag_error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=tag_error,
            )
        update_data = update_data.model_copy(update={"tags": normalized_tags})

    if "avatar_file_id" in provided_fields and update_data.avatar_file_id == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="参数错误",
        )

    if "avatar_display_mode" in provided_fields and update_data.avatar_display_mode is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="参数错误",
        )
    return update_data


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
    limit: int = Query(20, description="Number of items to return"),
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
    if limit < CONTACTS_LIMIT_MIN or limit > CONTACTS_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求参数错误",
        )

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

    except HTTPException:
        raise
    except ValueError as e:
        # Configuration error (e.g., im_conv_id not configured)
        logger.error(
            "contacts_list_config_error",
            user_qiao_id=current_user.qiao_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
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
            detail="系统错误",
        )


@router.get("/{conversation_id}", response_model=ContactDetailResponse)
async def get_contact(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Get specific contact details.

    Returns detailed information about a specific contact.

    Args:
        conversation_id: Conversation identifier
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
            conversation_id=conversation_id,
        )

        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="操作异常",
            )

        logger.info(
            "contact_detail_retrieved",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
        )

        return contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_detail_config_error",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    except Exception as e:
        logger.error(
            "contact_detail_failed",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.put("/{conversation_id}", response_model=ContactDetailResponse)
async def update_contact_info(
    conversation_id: str,
    update_data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Update contact information.

    Allows updating contact alias, tags, remark, pin status, mute status, and block status.
    All fields are optional - only provided fields will be updated.

    Args:
        conversation_id: Conversation identifier
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
        update_data = _normalize_and_validate_contact_update_payload_or_raise(update_data)

        updated_contact = await update_contact(
            db=db,
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            update_data=update_data,
        )

        if not updated_contact:
            logger.warning(
                "contact_update_not_found",
                user_qiao_id=current_user.qiao_id,
                conversation_id=conversation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_updated_via_api",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
        )

        return updated_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_update_config_error",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    except Exception as e:
        logger.error(
            "contact_update_failed",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.post("/{conversation_id}/block", response_model=ContactDetailResponse)
async def block_contact_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Block a contact.

    Blocks the specified contact, preventing messages from being received.

    Args:
        conversation_id: Conversation identifier
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
            conversation_id=conversation_id,
        )

        if not blocked_contact:
            logger.warning(
                "contact_block_not_found",
                user_qiao_id=current_user.qiao_id,
                conversation_id=conversation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_blocked_via_api",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
        )

        return blocked_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_block_config_error",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    except Exception as e:
        logger.error(
            "contact_block_failed",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.post("/{conversation_id}/unblock", response_model=ContactDetailResponse)
async def unblock_contact_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetailResponse:
    """Unblock a contact.

    Unblocks the specified contact, allowing messages to be received again.

    Args:
        conversation_id: Conversation identifier
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
            conversation_id=conversation_id,
        )

        if not unblocked_contact:
            logger.warning(
                "contact_unblock_not_found",
                user_qiao_id=current_user.qiao_id,
                conversation_id=conversation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_unblocked_via_api",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
        )

        return unblocked_contact

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(
            "contact_unblock_config_error",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    except Exception as e:
        logger.error(
            "contact_unblock_failed",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a contact.

    Soft deletes the contact relationship. Chat history is not deleted (managed by client).

    Args:
        conversation_id: Conversation identifier
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
            conversation_id=conversation_id,
        )

        if not success:
            logger.warning(
                "contact_delete_not_found",
                user_qiao_id=current_user.qiao_id,
                conversation_id=conversation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="操作异常",
            )

        logger.info(
            "contact_deleted_via_api",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
        )

        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "contact_delete_failed",
            user_qiao_id=current_user.qiao_id,
            conversation_id=conversation_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
