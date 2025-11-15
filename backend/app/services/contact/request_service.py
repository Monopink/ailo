"""
Contact request service business logic.

This module provides business logic for contact request processing.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from crud.contact import contact as contact_crud
from crud.contact import contact_request as contact_request_crud
from crud.user import user as user_crud
from crud.ai import ai_profile_template as ai_profile_template_crud
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
from services.message.outbound.helpers import send_chat_info, send_contact_request_notification
from services.contact.service import _get_im_conv_id, _get_contact_profile, _build_contact_response
from enums.templates import CHAT_INFO_TEMPLATES
from utils.logging import get_logger

logger = get_logger(__name__)


async def _get_contact_expiration_days(db: AsyncSession) -> int:
    """Read contact request expiration from configuration (stored in days)."""

    expiry_days_value = await system_configs.get_config_value(
        db, config_key="contact_request_expiration_days"
    )
    if expiry_days_value is None:
        logger.error("contact_request_expiration_config_missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统配置缺失",
        )

    return int(expiry_days_value)


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
        custom_avatar_url=None,
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
    # Capture for logging across transaction boundaries
    _req_id = contact_request.id
    _to_qiao_id = contact_request.to_qiao_id
    try:
        # Call AI module to handle request
        decision = await handle_ai_contact_request(
            db=db,
            request_id=contact_request.id,
            from_qiao_id=user_qiao_id,
            to_qiao_id=contact_request.to_qiao_id,
            message=contact_request.message or "",
        )

        # AI explicitly ignored (no response). Silent handling: keep pending, do not error out
        if not decision.accepted:
            logger.info(
                "ai_contact_request_ignored",
                request_id=_req_id,
                user_qiao_id=user_qiao_id,
                to_qiao_id=_to_qiao_id,
                reason=decision.reason,
            )
            return {"message": "请求已发送"}

        # AI accepted - create AI character and contact
        async with db.begin_nested():
            # Create AI character from template
            ai_character = await create_character_from_template(
                db=db,
                template_qiao_id=contact_request.to_qiao_id,
                user_qiao_id=user_qiao_id,
                user_id=user_id,
            )

            # Generate internal conversation ID
            from utils.snowflake import generate_snowflake_id

            conv_id = f"conv_{generate_snowflake_id()}"

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

            # Capture values before commit to avoid attribute expiration reloads
            _request_id = _req_id
            _ai_qiao_id = ai_character.qiao_id
            _contact_id = contact.id

        # Commit outer transaction once nested operations are done
        await db.commit()

        logger.info(
            "ai_contact_added",
            request_id=_request_id,
            user_qiao_id=user_qiao_id,
            ai_qiao_id=_ai_qiao_id,
            contact_id=_contact_id,
        )

        # Send CHAT_INFO message (best-effort; not in the same transaction)
        try:
            content = CHAT_INFO_TEMPLATES[ChatInfoType.CONTACT_ADDED]
            await send_chat_info(
                db=db,
                to_qiao_id=user_qiao_id,
                conv_id=conv_id,
                content=content,
            )
        except Exception as e:
            logger.error("send_chat_info_failed", request_id=_request_id, error=str(e))
            # Non-critical

        # Return success message
        return {"message": "请求已发送"}

    except ValueError as e:
        # Business validation failed (e.g., template unavailable, inactive, etc.)
        # Mark as IGNORED - this is expected business logic, not a system error
        await db.rollback()

        try:
            contact_request.status = ContactRequestStatus.IGNORED
            await db.commit()
        except Exception as commit_error:
            logger.error(
                "failed_to_mark_ignored",
                request_id=_req_id,
                error=str(commit_error),
            )

        logger.info(
            "ai_contact_request_ignored_validation_failed",
            request_id=_req_id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=_to_qiao_id,
            reason=str(e),
        )

        return {"message": "请求已发送"}

    except Exception as e:
        # Unexpected system error (database error, network error, code bug, etc.)
        # Mark as FAILED - this needs investigation and monitoring
        await db.rollback()

        try:
            contact_request.status = ContactRequestStatus.FAILED
            await db.commit()
        except Exception as commit_error:
            logger.error(
                "failed_to_mark_failed",
                request_id=_req_id,
                error=str(commit_error),
            )

        logger.error(
            "ai_contact_request_failed_system_error",
            request_id=_req_id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=_to_qiao_id,
            error=str(e),
            exc_info=True,
        )

        return {"message": "请求已发送"}


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


async def _check_and_restore_contact(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> Optional[dict]:
    """
    Check if contact already exists and restore if soft-deleted.

    Returns:
        Success message if contact exists/restored, None if should continue processing
    """
    existing = await contact_crud.get_user_contact_including_deleted(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=request.to_qiao_id
    )

    if not existing:
        return None

    if existing.is_deleted == 1:
        # Restore deleted contact
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


async def _check_ai_template_duplicate(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> Optional[dict]:
    """
    Check if user already created AI from this template.

    Returns:
        Success message if duplicate found and handled, None if should continue
    """
    try:
        result_ai = await db.execute(
            select(AICharacter.qiao_id, AICharacter.created_from_profile_qiao_id).where(
                AICharacter.user_qiao_id == user_qiao_id
            )
        )
        rows = result_ai.all()
        created_from_map = {}
        for qid, src in rows:
            if src:
                created_from_map[src] = qid

        if request.to_qiao_id in created_from_map:
            # Check if contact exists via character qiao_id
            existing_via_char = await contact_crud.get_user_contact_including_deleted(
                db,
                user_qiao_id=user_qiao_id,
                contact_qiao_id=created_from_map[request.to_qiao_id],
            )
            if existing_via_char:
                if existing_via_char.is_deleted == 1:
                    # Restore
                    restored_contact = await contact_crud.restore_contact(
                        db,
                        contact=existing_via_char,
                        alias=request.alias,
                        tags={"tags": request.tags} if request.tags else None,
                    )
                    logger.info(
                        "contact_restored_via_template",
                        user_qiao_id=user_qiao_id,
                        template_qiao_id=request.to_qiao_id,
                        contact_id=restored_contact.id,
                    )
                    return {"message": "请求已发送"}
                else:
                    logger.error(
                        "contact_already_exists_via_template",
                        user_qiao_id=user_qiao_id,
                        template_qiao_id=request.to_qiao_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="已添加该联系人",
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "template_dup_check_failed",
            user_qiao_id=user_qiao_id,
            to_qiao_id=request.to_qiao_id,
            error=str(e),
        )

    return None


async def _check_and_update_pending_request(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> Optional[dict]:
    """
    Check if pending/processing request exists and update it (idempotency).

    Returns:
        Success message if pending request updated, None if should create new
    """
    existing_request = await contact_request_crud.get_pending_request(
        db, from_qiao_id=user_qiao_id, to_qiao_id=request.to_qiao_id
    )

    if not existing_request:
        return None

    # Update existing pending/processing request
    try:
        existing_request.message = request.message
        existing_request.source = request.source
        # Extend expiry window
        expiry_days = await _get_contact_expiration_days(db)
        existing_request.expires_at = datetime.now() + timedelta(days=expiry_days)
        db.add(existing_request)
        await db.commit()

        logger.info(
            "pending_request_updated",
            user_qiao_id=user_qiao_id,
            to_qiao_id=request.to_qiao_id,
            request_id=existing_request.id,
            status=existing_request.status,
            expires_at=existing_request.expires_at,
        )
    except Exception as e:
        logger.error(
            "pending_request_update_failed",
            user_qiao_id=user_qiao_id,
            to_qiao_id=request.to_qiao_id,
            request_id=existing_request.id,
            error=str(e),
        )

    return {"message": "请求已发送"}


async def _determine_target_type(
    db: AsyncSession,
    to_qiao_id: str,
) -> ContactType:
    """
    Determine if target is USER or AI by querying database.

    Returns:
        ContactType.USER or ContactType.AI

    Raises:
        HTTPException: If target not found
    """
    # Try user first
    target_user = await user_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
    if target_user:
        return ContactType.USER

    # Try AI profile template
    template = await ai_profile_template_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
    if template and int(template.status) == 1:
        return ContactType.AI

    logger.error("target_not_found", to_qiao_id=to_qiao_id)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="目标用户不存在",
    )


async def _validate_ai_contact_limit(
    db: AsyncSession,
    user_qiao_id: str,
    target_type: ContactType,
) -> None:
    """
    Validate AI contact limit if target is AI.

    Raises:
        HTTPException: If limit exceeded
    """
    if target_type != ContactType.AI:
        return

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


async def _create_request_record(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
    target_type: ContactType,
) -> ContactRequest:
    """
    Create contact request record in database.

    Returns:
        Created ContactRequest object
    """
    # Get user info
    user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
    if not user:
        logger.error("user_not_found", user_qiao_id=user_qiao_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户不存在",
        )

    # Calculate expiration time
    expiry_days = await _get_contact_expiration_days(db)
    expires_at = datetime.now() + timedelta(days=expiry_days)

    # Create contact request record
    contact_request_obj = ContactRequest(
        from_qiao_id=user_qiao_id,
        from_type=ContactType.USER,
        from_id=user.id,
        to_qiao_id=request.to_qiao_id,
        to_type=target_type,
        to_id=None,
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

    return contact_request_obj


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
    # Stage 1: Check if contact already exists (including soft-deleted)
    if result := await _check_and_restore_contact(db, user_qiao_id, request):
        return result

    # Stage 2: Check if user already created AI from this template
    if result := await _check_ai_template_duplicate(db, user_qiao_id, request):
        return result

    # Stage 3: Check if pending/processing request exists (idempotency)
    if result := await _check_and_update_pending_request(db, user_qiao_id, request):
        return result

    # Stage 4: Determine target type and validate
    target_type = await _determine_target_type(db, request.to_qiao_id)
    await _validate_ai_contact_limit(db, user_qiao_id, target_type)

    # Stage 5: Create request record
    contact_request = await _create_request_record(db, user_qiao_id, request, target_type)

    # Stage 6: Route to appropriate handler
    if target_type == ContactType.AI:
        # Enqueue for background worker
        await db.commit()
        logger.info(
            "ai_contact_request_enqueued",
            request_id=contact_request.id,
            user_qiao_id=user_qiao_id,
            to_qiao_id=request.to_qiao_id,
        )
        return {"message": "请求已发送"}
    else:
        # Process user contact request immediately
        return await _process_user_contact_request(
            db=db,
            user_qiao_id=user_qiao_id,
            contact_request=contact_request,
        )


# Background processing moved to services.contact.request_worker


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
        conv_id = await _get_im_conv_id(db, ensure_valid=True)
        tags_dict = {"tags": accept_data.tags} if accept_data.tags else None

        contact_data = ContactCreate(
            contact_type=ContactType(contact_request.from_type),
            contact_qiao_id=contact_request.from_qiao_id,
            alias=accept_data.alias,
            custom_avatar_url=None,
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

        # Update request status to ignored (user rejected)
        await contact_request_crud.update_request_status(
            db, request_id=request_id, status=ContactRequestStatus.IGNORED
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
