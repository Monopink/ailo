"""
Contact request service business logic.

This module provides business logic for contact request processing.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ai import ai_persona as ai_persona_crud
from app.crud.contact import contact as contact_crud
from app.crud.contact import contact_request as contact_request_crud
from app.crud.profile import profile as profile_crud
from app.crud.user import user as user_crud
from app.enums import (
    CHAT_INFO_TEMPLATES,
    AIPersonaStatus,
    ChatInfoType,
    ContactRequestStatus,
    ContactSource,
    ContactType,
)
from app.models.ai.instance import AIInstance
from app.models.contact import Contact, ContactRequest
from app.schemas.contact import (
    ContactCreate,
    ContactDetailResponse,
    ContactProfileSummary,
    ContactRequestAccept,
    ContactRequestCreate,
    ContactRequestListResponse,
    ContactRequestWithProfile,
)
from app.services.contact.service import get_contact_with_profile
from app.services.entitlement.service import (
    ENTITLEMENT_AI_CONTACT_LIMIT,
    ENTITLEMENT_SOURCE_CONTACT_AI_SLOT,
    consume_entitlement,
)
from app.services.entitlement.service import (
    get_ai_contact_limit as get_ai_contact_limit_by_user_id,
)
from app.services.message.outbound.helpers import send_chat_info, send_contact_request_notification
from app.services.profile.avatar import get_avatar_url
from app.services.system_config import get_config_int
from app.type_defs import JSONDict, JSONValue
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


async def _get_contact_expiration_days(db: AsyncSession) -> int:
    """Read contact request expiration from configuration (stored in days)."""
    expiry = await get_config_int(db, key="contact_request_expiration_days")
    if expiry < 1:
        logger.error("contact_request_expiration_config_invalid", value=expiry)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )

    return expiry


async def get_ai_contact_limit(db: AsyncSession, user_qiao_id: str) -> int:
    """
    Get available AI contact slots for user.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id

    Returns:
        Available AI contact slots

    Raises:
        ValueError: If limit not configured
    """
    user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
    if not user:
        logger.error("user_not_found_for_contact_limit", user_qiao_id=user_qiao_id)
        raise ValueError("User not found")

    return await get_ai_contact_limit_by_user_id(db, user_id=user.id)


def _build_request_tags_payload(tags: list[str] | None) -> JSONDict | None:
    if tags is None:
        return None
    normalized_tags: list[JSONValue] = list(tags)
    return {"tags": normalized_tags}


async def _consume_ai_slot_for_restored_contact(
    db: AsyncSession,
    *,
    user_id: int,
    contact: Contact,
    request_to_qiao_id: str,
    restore_token_ms: int,
) -> None:
    available_total = await get_ai_contact_limit_by_user_id(db, user_id=user_id)
    if available_total <= 0:
        logger.error(
            "ai_contact_limit_exceeded_restore",
            user_id=user_id,
            contact_id=contact.id,
            available_total=available_total,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="联系人数量已达上限",
        )

    await consume_entitlement(
        db,
        user_id=user_id,
        entitlement_type_code=ENTITLEMENT_AI_CONTACT_LIMIT,
        value=1,
        source_type=ENTITLEMENT_SOURCE_CONTACT_AI_SLOT,
        source_id=int(contact.id),
        idempotency_key=f"contact_ai_restore_consume:{int(contact.id)}:{restore_token_ms}",
        event_payload={
            "contact_qiao_id": request_to_qiao_id,
            "restore_token_ms": restore_token_ms,
        },
    )


async def _process_user_contact_request(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    contact_request: "ContactRequest",
) -> JSONDict:
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
) -> JSONDict | None:
    """
    Check if contact already exists and restore if soft-deleted.

    Returns:
        Success message if contact exists/restored, None if should continue processing
    """
    existing = await contact_crud.get_user_contact_including_deleted(
        db,
        user_qiao_id=user_qiao_id,
        contact_qiao_id=request.to_qiao_id,
        for_update=True,
    )

    if not existing:
        return None

    if existing.is_deleted == 1:
        if existing.deleted_at is None:
            logger.error(
                "contact_deleted_at_missing_for_restore",
                user_qiao_id=user_qiao_id,
                contact_id=existing.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统错误",
            )
        restore_token_ms = int(existing.deleted_at.astimezone(UTC).timestamp() * 1000)

        # Restore deleted contact
        restored_contact = await contact_crud.restore_contact(
            db,
            contact=existing,
            alias=request.alias,
        )
        if int(restored_contact.contact_type) == int(ContactType.AI):
            owner_user_id = (
                int(restored_contact.user_id) if restored_contact.user_id is not None else None
            )
            if owner_user_id is None:
                owner_user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
                if owner_user is None:
                    logger.error("user_not_found_for_restore", user_qiao_id=user_qiao_id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="用户不存在",
                    )
                owner_user_id = int(owner_user.id)
            await _consume_ai_slot_for_restored_contact(
                db,
                user_id=owner_user_id,
                contact=restored_contact,
                request_to_qiao_id=request.to_qiao_id,
                restore_token_ms=restore_token_ms,
            )
        await db.commit()
        logger.info(
            "contact_restored",
            user_qiao_id=user_qiao_id,
            contact_qiao_id=request.to_qiao_id,
            contact_id=restored_contact.id,
        )
        return {"message": "请求已发送"}
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


async def _check_ai_persona_duplicate(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> JSONDict | None:
    """
    Check if the user already instantiated the requested persona.

    Returns:
        Success message if duplicate found/restored, None if new persona should be created.
    """

    persona = await ai_persona_crud.get_by_qiao_id(db, qiao_id=request.to_qiao_id)
    if not persona:
        return None

    try:
        stmt = (
            select(Contact, AIInstance)
            .join(AIInstance, AIInstance.id == Contact.contact_id)
            .where(
                Contact.user_qiao_id == user_qiao_id,
                Contact.contact_type == ContactType.AI,
                AIInstance.persona_id == persona.id,
            )
            .order_by(Contact.id.desc())
            .limit(1)
            .with_for_update(of=Contact)
        )

        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None

        existing_contact, _ = row

        if existing_contact.is_deleted == 1:
            if existing_contact.deleted_at is None:
                logger.error(
                    "persona_contact_deleted_at_missing_for_restore",
                    user_qiao_id=user_qiao_id,
                    contact_id=existing_contact.id,
                    persona_id=persona.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="系统错误",
                )
            restore_token_ms = int(existing_contact.deleted_at.astimezone(UTC).timestamp() * 1000)
            restored_contact = await contact_crud.restore_contact(
                db,
                contact=existing_contact,
                alias=request.alias,
            )
            owner_user_id = (
                int(restored_contact.user_id) if restored_contact.user_id is not None else None
            )
            if owner_user_id is None:
                owner_user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
                if owner_user is None:
                    logger.error("user_not_found_for_persona_restore", user_qiao_id=user_qiao_id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="用户不存在",
                    )
                owner_user_id = int(owner_user.id)
            await _consume_ai_slot_for_restored_contact(
                db,
                user_id=owner_user_id,
                contact=restored_contact,
                request_to_qiao_id=request.to_qiao_id,
                restore_token_ms=restore_token_ms,
            )
            await db.commit()
            logger.info(
                "contact_restored_via_persona",
                user_qiao_id=user_qiao_id,
                persona_id=persona.id,
                contact_id=restored_contact.id,
            )
            return {"message": "请求已发送"}

        # If we reach here without returning, contact exists and is not deleted
    except Exception as exc:
        logger.error(
            "persona_dup_check_failed",
            user_qiao_id=user_qiao_id,
            persona_id=persona.id,
            error=str(exc),
        )
        raise
    else:
        # Only executed if no exception and no early return
        # Contact exists and is not deleted - this is an error case
        logger.error(
            "contact_already_exists_via_persona",
            user_qiao_id=user_qiao_id,
            persona_id=persona.id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已添加该联系人",
        )


async def _check_and_update_pending_request(
    db: AsyncSession,
    user_qiao_id: str,
    request: ContactRequestCreate,
) -> JSONDict | None:
    """
    Check if non-finished request exists (idempotency).

    Returns:
        Success message if request is already in-flight, None if should create new
    """
    existing_request = await contact_request_crud.get_pending_request(
        db, from_qiao_id=user_qiao_id, to_qiao_id=request.to_qiao_id
    )

    if not existing_request:
        return None

    logger.info(
        "contact_request_duplicate_ignored",
        user_qiao_id=user_qiao_id,
        to_qiao_id=request.to_qiao_id,
        request_id=existing_request.id,
        status=int(existing_request.status),
        failure_code=existing_request.failure_code,
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

    # Try AI persona record
    persona = await ai_persona_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
    if persona and int(persona.status) == AIPersonaStatus.ACTIVE:
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

    available_total = await get_ai_contact_limit(db, user_qiao_id)
    if available_total <= 0:
        logger.error(
            "ai_contact_limit_exceeded",
            user_qiao_id=user_qiao_id,
            available_total=available_total,
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
    expires_at = datetime.now(UTC) + timedelta(days=expiry_days)

    # Create contact request record
    contact_request_obj = ContactRequest(
        from_qiao_id=user_qiao_id,
        from_type=ContactType.USER,
        from_id=user.id,
        to_qiao_id=request.to_qiao_id,
        to_type=target_type,
        to_id=None,
        message=request.message,
        category_key=request.category_key,
        alias=request.alias,
        tags=_build_request_tags_payload(request.tags),
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
) -> JSONDict:
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
    if result := await _check_and_restore_contact(db, user_qiao_id, request):
        return result

    target_type = await _determine_target_type(db, request.to_qiao_id)
    await _validate_ai_contact_limit(db, user_qiao_id, target_type)

    if target_type == ContactType.AI and (
        result := await _check_ai_persona_duplicate(db, user_qiao_id, request)
    ):
        return result

    if result := await _check_and_update_pending_request(db, user_qiao_id, request):
        return result

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
    # Process user contact request immediately
    return await _process_user_contact_request(
        db=db,
        user_qiao_id=user_qiao_id,
        contact_request=contact_request,
    )


async def get_contact_requests_service(
    db: AsyncSession,
    user_qiao_id: str,
    status_filter: ContactRequestStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> ContactRequestListResponse:
    """
    Get user's received contact requests with applicant profiles.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        status_filter: Filter by request status
        skip: Offset for pagination
        limit: Number of items to return

    Returns:
        ContactRequestListResponse with items and pagination info

    Raises:
        HTTPException: If query fails
    """
    try:
        if skip < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参数错误")

        # Get contact requests
        requests = await contact_request_crud.get_user_received_requests(
            db, to_qiao_id=user_qiao_id, status=status_filter, skip=skip, limit=limit + 1
        )

        # Check if there are more items
        has_more = len(requests) > limit
        if has_more:
            requests = requests[:limit]

        next_skip = skip + len(requests) if has_more else None

        # Build response items with profiles
        items = []
        for req in requests:
            # Get applicant profile
            profile = await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=req.from_qiao_id)

            # Build profile info
            avatar_url = await get_avatar_url(profile)

            from_profile = ContactProfileSummary(
                nickname=profile.nickname if profile else None,
                avatar_url=avatar_url,
                gender=profile.gender if profile else None,
                bio=profile.bio if profile else None,
                region=profile.region if profile else None,
            )

            # Build request item
            item = ContactRequestWithProfile(
                id=req.id,
                from_qiao_id=req.from_qiao_id,
                message=req.message,
                status=ContactRequestStatus(req.status),
                created_at=req.created_at,
                from_profile=from_profile,
            )
            items.append(item)

        # Build pagination info
        pagination = {
            "has_more": has_more,
            "next_skip": next_skip,
        }

        logger.info(
            "get_contact_requests_success",
            user_qiao_id=user_qiao_id,
            status_filter=status_filter,
            count=len(items),
            skip=skip,
            limit=limit,
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
            detail="系统错误",
        ) from e


async def accept_contact_request_service(
    db: AsyncSession,
    user_qiao_id: str,
    request_id: int,
    accept_data: ContactRequestAccept,
) -> ContactDetailResponse:
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

    def _raise_request_not_found() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="请求不存在",
        )

    def _raise_forbidden() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="无权操作此请求",
        )

    def _raise_invalid_status() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="请求状态不正确",
        )

    def _raise_contact_exists() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="已添加该联系人",
        )

    def _raise_user_not_found() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    def _raise_sync_failed() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )

    try:
        # Get contact request
        contact_request = await contact_request_crud.get(db, record_id=request_id)
        if not contact_request:
            _raise_request_not_found()
        assert contact_request is not None

        # Verify request is for current user
        if contact_request.to_qiao_id != user_qiao_id:
            _raise_forbidden()

        # Verify request status
        if contact_request.status != ContactRequestStatus.PENDING:
            _raise_invalid_status()

        # Check if contact already exists
        existing = await contact_crud.get_user_contact(
            db, user_qiao_id=user_qiao_id, contact_qiao_id=contact_request.from_qiao_id
        )
        if existing:
            _raise_contact_exists()

        # Get user info
        user = await user_crud.get_by_qiao_id(db, qiao_id=user_qiao_id)
        if not user:
            _raise_user_not_found()
        assert user is not None

        # Create contact conversation_id.
        # If reverse contact already exists (applicant -> current user), reuse its conversation_id.
        reverse_contact = await contact_crud.get_user_contact(
            db,
            user_qiao_id=contact_request.from_qiao_id,
            contact_qiao_id=user_qiao_id,
        )
        conversation_id = (
            reverse_contact.conversation_id
            if reverse_contact
            else f"conv_{generate_snowflake_id()}"
        )

        contact_data = ContactCreate(
            contact_type=ContactType(contact_request.from_type),
            contact_qiao_id=contact_request.from_qiao_id,
            alias=accept_data.alias,
            custom_avatar_key=None,
            custom_avatar_media_id=None,
            tags=accept_data.tags,
            remark=None,
            source=ContactSource.CONTACT_REQUEST,
        )

        contact = await contact_crud.create_with_user(
            db,
            obj_in=contact_data,
            user_qiao_id=user_qiao_id,
            user_id=user.id,
            conversation_id=conversation_id,
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
                conversation_id=conversation_id,
                content=content,
            )
        except Exception as e:
            logger.error(
                "send_chat_info_failed",
                request_id=request_id,
                error=str(e),
            )
            # Non-critical, continue

        # Build response payload
        contact_response = await get_contact_with_profile(
            db=db,
            user_qiao_id=user_qiao_id,
            conversation_id=contact.conversation_id,
        )
        if not contact_response:
            _raise_sync_failed()
        assert contact_response is not None

        logger.info(
            "accept_contact_request_success",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
            contact_id=contact.id,
        )

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
            detail="系统错误",
        ) from e
    else:
        return contact_response


async def ignore_contact_request_service(
    db: AsyncSession,
    user_qiao_id: str,
    request_id: int,
) -> JSONDict:
    """
    Ignore a contact request without notifying the applicant.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id (the one ignoring)
        request_id: Contact request ID

    Returns:
        Success message: {"message": "已忽略"}

    Raises:
        HTTPException: If request not found, invalid status, or processing fails
    """

    def _raise_request_not_found() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="请求不存在",
        )

    def _raise_forbidden() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="无权操作此请求",
        )

    def _raise_invalid_status() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="请求状态不正确",
        )

    try:
        # Get contact request
        contact_request = await contact_request_crud.get(db, record_id=request_id)
        if not contact_request:
            _raise_request_not_found()
        assert contact_request is not None

        # Verify request is for current user
        if contact_request.to_qiao_id != user_qiao_id:
            _raise_forbidden()

        # Verify request status
        if contact_request.status != ContactRequestStatus.PENDING:
            _raise_invalid_status()

        # Update request status to ignored
        await contact_request_crud.update_request_status(
            db, request_id=request_id, status=ContactRequestStatus.IGNORED
        )

        logger.info(
            "ignore_contact_request_success",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "ignore_contact_request_failed",
            user_qiao_id=user_qiao_id,
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        ) from e
    else:
        return {"message": "已忽略"}
