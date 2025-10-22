"""
Contact request service business logic.

This module provides business logic for contact request processing.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from crud.contact import contact as contact_crud
from crud.contact import contact_request as contact_request_crud
from crud.user import user as user_crud
from crud.profile import profile as profile_crud
from crud.system import system_configs
from models.contact import Contact, ContactRequest
from models.ai.character import AICharacter
from enums import ContactType, ContactRequestStatus, ChatInfoType, ProfileOwnerType
from schemas.contact import (
    ContactRequestCreate,
    ContactCreate,
    ContactRequestWithProfile,
    ContactRequestListResponse,
    ContactRequestAccept,
    ContactResponse,
)
from schemas.contact import ContactInfoBase
from services.ai.character_creation import create_character_from_template
from services.ai.contact_handler import handle_ai_contact_request
from services.message.convenience import send_chat_info, send_contact_request_notification
from services.contact.service import _get_im_conv_id, _get_contact_profile, _build_contact_response
from enums.templates import CHAT_INFO_TEMPLATES
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_ai_contact_limit(db: AsyncSession, user_qiao_id: str) -> int:
    """
    Get AI contact limit for user.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id

    Returns:
        AI contact limit

    Raises:
        ValueError: If limit not configured
    """
    limit = await system_configs.get_config_value(db, config_key="default_contact_limit")

    if limit is None:
        logger.error("contact_limit_config_not_found", user_qiao_id=user_qiao_id)
        raise ValueError("Contact limit not configured")

    return int(limit)


async def _create_contact_record(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    user_id: int,
    contact_qiao_id: str,
    contact_id: int,
    contact_type: ContactType,
    conv_id: str,
    alias: Optional[str],
    tags: Optional[List[str]],
) -> Contact:
    """
    Create contact record.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        user_id: User's internal ID
        contact_qiao_id: Contact's qiao_id
        contact_id: Contact's internal ID
        contact_type: Contact type
        conv_id: Conversation ID
        alias: Contact alias
        tags: Contact tags

    Returns:
        Created contact
    """
    contact_data = ContactCreate(
        contact_type=contact_type,
        contact_qiao_id=contact_qiao_id,
        alias=alias,
        avatar_alias_url=None,
        tags={"tags": tags} if tags else None,
        remark=None,
    )

    contact = await contact_crud.create_with_user(
        db, obj_in=contact_data, user_qiao_id=user_qiao_id, user_id=user_id, conv_id=conv_id
    )

    # Update contact_id
    contact.contact_id = contact_id
    db.add(contact)

    return contact


# ============================================================================
# Contact Request Processing
# ============================================================================


async def _process_ai_contact_request(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    user_id: int,
    contact_request: "ContactRequest",
    alias: Optional[str],
    tags: Optional[List[str]],
) -> dict:
    """
    Process AI contact request.

    Calls AI module for validation and decision.
    If accepted, creates AI character and contact record.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        user_id: User's internal ID
        contact_request: Contact request record
        alias: Contact alias
        tags: Contact tags

    Returns:
        Success message: {"message": "请求已发送"}

    Raises:
        HTTPException: If AI validation fails or processing error occurs
    """
    try:
        # Call AI module to handle request
        decision = await handle_ai_contact_request(
            db=db,
            request_id=contact_request.id,
            from_qiao_id=user_qiao_id,
            to_qiao_id=contact_request.to_qiao_id,
            message=contact_request.message or "",
        )

        # AI explicitly ignored (no response)
        if not decision.accepted:
            contact_request.status = ContactRequestStatus.IGNORED
            await db.commit()

            logger.info(
                "ai_contact_request_ignored",
                request_id=contact_request.id,
                user_qiao_id=user_qiao_id,
                to_qiao_id=contact_request.to_qiao_id,
                reason=decision.reason,
            )

            # User receives no notification (similar to no response)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="添加失败，请稍后再试",
            )

        # AI accepted - create AI character and contact
        async with db.begin_nested():
            # Create AI character from template
            ai_character = await create_character_from_template(
                db=db, template_qiao_id=contact_request.to_qiao_id, user_qiao_id=user_qiao_id
            )

            # Get conversation ID
            conv_id = await _get_im_conv_id(db)

            # Create contact record
            contact = await _create_contact_record(
                db=db,
                user_qiao_id=user_qiao_id,
                user_id=user_id,
                contact_qiao_id=ai_character.qiao_id,
                contact_id=ai_character.id,
                contact_type=ContactType.AI,
                conv_id=conv_id,
                alias=alias,
                tags=tags,
            )

            # Update contact request status
            contact_request.status = ContactRequestStatus.ACCEPTED
            contact_request.to_id = ai_character.id

            await db.commit()

            logger.info(
                "ai_contact_added",
                request_id=contact_request.id,
                user_qiao_id=user_qiao_id,
                ai_qiao_id=ai_character.qiao_id,
                contact_id=contact.id,
            )

            # Send CHAT_INFO message
            content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
            await send_chat_info(
                db=db,
                to_qiao_id=user_qiao_id,
                conv_id=conv_id,
                content=content,
            )

            # Return success message
            return {"message": "请求已发送"}

    except ValueError as e:
        # AI validation failed - AI module already logged error
        # Do not update contact_request status (let it expire naturally)
        await db.rollback()

        logger.error(
            "ai_contact_request_validation_failed",
            request_id=contact_request.id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=contact_request.to_qiao_id,
            error=str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="添加失败，请稍后再试",
        )

    except Exception as e:
        # Unexpected error
        await db.rollback()

        logger.error(
            "ai_contact_request_processing_error",
            request_id=contact_request.id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=contact_request.to_qiao_id,
            error=str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误，请稍后再试",
        )


async def _process_user_contact_request(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    contact_request: "ContactRequest",
) -> dict:
    """
    Process user contact request.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        contact_request: Contact request record

    Returns:
        Success message

    Raises:
        HTTPException: If processing error occurs
    """
    # Validate target user exists
    target_user = await user_crud.get_by_qiao_id(db, qiao_id=contact_request.to_qiao_id)
    if not target_user:
        logger.error(
            "target_user_not_found",
            request_id=contact_request.id,
            to_qiao_id=contact_request.to_qiao_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户不存在",
        )

    # Send notification message
    try:
        await send_contact_request_notification(
            db=db,
            to_qiao_id=contact_request.to_qiao_id,
            from_qiao_id=user_qiao_id,
            request_id=contact_request.id,
            message=contact_request.message or "",
        )
    except Exception as e:
        logger.error(
            "notification_send_exception",
            request_id=contact_request.id,
            error=str(e),
        )
        # Non-critical, continue

    await db.commit()

    logger.info(
        "user_contact_request_sent",
        request_id=contact_request.id,
        user_qiao_id=user_qiao_id,
        to_qiao_id=contact_request.to_qiao_id,
    )

    return {"message": "请求已发送"}


async def create_contact_request_service(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> dict:
    """
    Unified contact request handler.

    This function handles both AI and user contact requests with unified logic.
    All requests create a contact_request record and return a success message.
    The actual contact is created only after acceptance (AI auto-accepts, user manual accepts).

    Args:
        db: Database session
        user_qiao_id: Requester's qiao_id
        request: Contact request data

    Returns:
        Success message: {"message": "请求已发送"}

    Raises:
        HTTPException: If validation fails or request cannot be processed
    """
    # ========== Stage 1: Pre-validation ==========

    # 1.1 Check if contact already exists (including deleted)
    existing = await contact_crud.get_user_contact_including_deleted(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=request.to_qiao_id
    )

    if existing:
        if existing.is_deleted == 1:
            # Restore deleted contact with new settings
            # Convert tags from List[str] to dict format
            tags_dict = {"tags": request.tags} if request.tags else None

            restored_contact = await contact_crud.restore_contact(
                db,
                contact=existing,
                alias=request.alias,
                tags=tags_dict,
            )

            logger.info(
                "contact_restored",
                user_qiao_id=user_qiao_id,
                contact_qiao_id=request.to_qiao_id,
                contact_id=restored_contact.id,
            )

            # Return success message
            return {"message": "请求已发送"}
        else:
            # Contact already exists and not deleted
            logger.error(
                "contact_already_exists",
                user_qiao_id=user_qiao_id,
                to_qiao_id=request.to_qiao_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已添加该联系人",
            )

    # 1.1.5 Check if pending request already exists
    existing_request = await contact_request_crud.get_pending_request(
        db, from_qiao_id=user_qiao_id, to_qiao_id=request.to_qiao_id
    )
    if existing_request:
        # Check if request is still valid (not expired)
        now = datetime.now(timezone.utc)
        if existing_request.expires_at and existing_request.expires_at > now:
            logger.info(
                "pending_request_already_exists",
                user_qiao_id=user_qiao_id,
                to_qiao_id=request.to_qiao_id,
                request_id=existing_request.id,
                expires_at=existing_request.expires_at,
            )
            # Return success but don't create new request
            return {"message": "请求已发送"}
        else:
            # Request expired, can create new one
            logger.info(
                "previous_request_expired",
                user_qiao_id=user_qiao_id,
                to_qiao_id=request.to_qiao_id,
                request_id=existing_request.id,
            )

    # 1.2 Determine target type by querying database
    # Try user first
    target_user = await user_crud.get_by_qiao_id(db, qiao_id=request.to_qiao_id)
    if target_user:
        target_type = ContactType.USER
    else:
        # Try AI character
        result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == request.to_qiao_id))
        character = result.scalar_one_or_none()
        if character:
            target_type = ContactType.AI
        else:
            logger.error("target_not_found", to_qiao_id=request.to_qiao_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="目标用户不存在",
            )

    # 1.3 AI contact: Check limit
    if target_type == ContactType.AI:
        limit = await get_ai_contact_limit(db, user_qiao_id)
        current_count = await contact_crud.count_user_contacts(
            db, user_qiao_id=user_qiao_id, contact_type=ContactType.AI
        )
        if current_count >= limit:
            logger.error(
                "ai_contact_limit_exceeded",
                user_qiao_id=user_qiao_id,
                current_count=current_count,
                limit=limit,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="联系人数量已达上限",
            )

    # ========== Stage 2: Create request record ==========

    # Get user info
    user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
    if not user:
        logger.error("user_not_found", user_qiao_id=user_qiao_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户不存在",
        )

    # Calculate expiration time
    expiry_days_config = await system_configs.get_config_value(db, config_key="contact_request_expiry_days")
    expiry_days = int(expiry_days_config) if expiry_days_config else 3
    expires_at = datetime.now() + timedelta(days=expiry_days)

    # Create contact request record
    contact_request_obj = ContactRequest(
        from_qiao_id=user_qiao_id,
        from_type=ContactType.USER,
        from_id=user.id,
        to_qiao_id=request.to_qiao_id,
        to_type=target_type,
        to_id=None,  # Leave empty
        message=request.message,
        source=request.source,
        status=ContactRequestStatus.PENDING,
        expires_at=expires_at,
    )

    db.add(contact_request_obj)
    await db.flush()  # Get request ID

    logger.info(
        "contact_request_created",
        request_id=contact_request_obj.id,
        user_qiao_id=user_qiao_id,
        to_qiao_id=request.to_qiao_id,
        target_type=target_type,
    )

    # ========== Stage 3: Process request ==========

    if target_type == ContactType.AI:
        # AI contact request processing
        return await _process_ai_contact_request(
            db=db,
            user_qiao_id=user_qiao_id,
            user_id=user.id,
            contact_request=contact_request_obj,
            alias=request.alias,
            tags=request.tags,
        )
    else:
        # User contact request processing
        return await _process_user_contact_request(
            db=db,
            user_qiao_id=user_qiao_id,
            contact_request=contact_request_obj,
        )


async def get_contact_requests_service(
    db: AsyncSession,
    user_qiao_id: str,
    status_filter: Optional[ContactRequestStatus] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> ContactRequestListResponse:
    """
    Get user's received contact requests with applicant profiles.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        status_filter: Filter by request status
        cursor: Pagination cursor (not implemented yet, using skip)
        limit: Number of items to return

    Returns:
        ContactRequestListResponse with items and pagination info

    Raises:
        HTTPException: If query fails
    """
    try:
        # Get contact requests
        # TODO: Implement cursor-based pagination
        skip = 0
        requests = await contact_request_crud.get_user_received_requests(
            db, to_qiao_id=user_qiao_id, status=status_filter, skip=skip, limit=limit + 1
        )

        # Check if there are more items
        has_more = len(requests) > limit
        if has_more:
            requests = requests[:limit]

        # Build response items with profiles
        items = []
        for req in requests:
            # Get applicant profile
            profile_owner_type = (
                ProfileOwnerType.USER if req.from_type == ContactType.USER else ProfileOwnerType.AI
            )
            profile = await profile_crud.get_by_owner_qiao_id(
                db, owner_qiao_id=req.from_qiao_id, owner_type=profile_owner_type
            )

            # Build profile info
            from_profile = ContactInfoBase(
                nickname=profile.nickname if profile else None,
                avatar_url=profile.avatar_url if profile else None,
                gender=profile.gender if profile else None,
            )

            # Build request item
            item = ContactRequestWithProfile(
                id=req.id,
                from_qiao_id=req.from_qiao_id,
                from_type=ContactType(req.from_type),
                message=req.message,
                status=ContactRequestStatus(req.status),
                created_at=req.created_at,
                from_profile=from_profile,
            )
            items.append(item)

        # Build pagination info
        pagination = {
            "cursor": None,  # TODO: Implement cursor
            "has_more": has_more,
        }

        logger.info(
            "get_contact_requests_success",
            user_qiao_id=user_qiao_id,
            status_filter=status_filter,
            count=len(items),
        )

        return ContactRequestListResponse(items=items, pagination=pagination)

    except Exception as e:
        logger.error(
            "get_contact_requests_failed",
            user_qiao_id=user_qiao_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取请求列表失败",
        )


async def accept_contact_request_service(
    db: AsyncSession,
    user_qiao_id: str,
    request_id: int,
    accept_data: ContactRequestAccept,
) -> ContactResponse:
    """
    Accept a contact request and create contact relationship.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id (the one accepting)
        request_id: Contact request ID
        accept_data: Accept data with alias and tags

    Returns:
        ContactResponse with created contact info

    Raises:
        HTTPException: If request not found, invalid status, or processing fails
    """
    from fastapi import status as http_status

    try:
        # Get contact request
        contact_request = await contact_request_crud.get(db, id=request_id)
        if not contact_request:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="请求不存在",
            )

        # Verify request is for current user
        if contact_request.to_qiao_id != user_qiao_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="无权操作此请求",
            )

        # Verify request status
        if contact_request.status != ContactRequestStatus.PENDING:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="请求状态不正确",
            )

        # Check if contact already exists
        existing = await contact_crud.get_user_contact(
            db, user_qiao_id=user_qiao_id, contact_qiao_id=contact_request.from_qiao_id
        )
        if existing:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="已添加该联系人",
            )

        # Get user info
        user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
        if not user:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        # Create contact
        conv_id = await _get_im_conv_id(db)
        tags_dict = {"tags": accept_data.tags} if accept_data.tags else None

        contact_data = ContactCreate(
            contact_type=ContactType(contact_request.from_type),
            contact_qiao_id=contact_request.from_qiao_id,
            alias=accept_data.alias,
            avatar_alias_url=None,
            tags=tags_dict,
            remark=None,
        )

        contact = await contact_crud.create_with_user(
            db,
            obj_in=contact_data,
            user_qiao_id=user_qiao_id,
            user_id=user.id,
            conv_id=conv_id,
        )

        # Update request status
        await contact_request_crud.update_request_status(
            db, request_id=request_id, status=ContactRequestStatus.ACCEPTED
        )

        # Send CHAT_INFO message to applicant
        try:
            content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
            await send_chat_info(
                db=db,
                to_qiao_id=contact_request.from_qiao_id,
                conv_id=conv_id,
                content=content,
            )
        except Exception as e:
            logger.error(
                "send_chat_info_failed",
                request_id=request_id,
                error=str(e),
            )
            # Non-critical, continue

        # Get profile and build response
        profile = await _get_contact_profile(db, contact.contact_qiao_id, ContactType(contact.contact_type))

        logger.info(
            "accept_contact_request_success",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
            contact_id=contact.id,
        )

        return _build_contact_response(contact, conv_id, profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "accept_contact_request_failed",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="接受请求失败",
        )


async def reject_contact_request_service(
    db: AsyncSession,
    user_qiao_id: str,
    request_id: int,
) -> dict:
    """
    Reject a contact request.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id (the one rejecting)
        request_id: Contact request ID

    Returns:
        Success message: {"message": "已拒绝"}

    Raises:
        HTTPException: If request not found, invalid status, or processing fails
    """
    from fastapi import status as http_status

    try:
        # Get contact request
        contact_request = await contact_request_crud.get(db, id=request_id)
        if not contact_request:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="请求不存在",
            )

        # Verify request is for current user
        if contact_request.to_qiao_id != user_qiao_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="无权操作此请求",
            )

        # Verify request status
        if contact_request.status != ContactRequestStatus.PENDING:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="请求状态不正确",
            )

        # Update request status to rejected
        await contact_request_crud.update_request_status(
            db, request_id=request_id, status=ContactRequestStatus.REJECTED
        )

        logger.info(
            "reject_contact_request_success",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
        )

        return {"message": "已拒绝"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "reject_contact_request_failed",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="拒绝请求失败",
        )
