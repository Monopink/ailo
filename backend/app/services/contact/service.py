"""
Contact service business logic.

This module provides business logic for contact management operations.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.crud.profile import profile as profile_crud
from app.enums import ContactType
from app.models.contact import Contact
from app.models.profile import Profile
from app.schemas.contact import (
    ContactDetailResponse,
    ContactListItem,
    ContactProfileSummary,
    ContactUpdate,
)
from app.services.profile.avatar import get_avatar_url, get_avatar_urls_batch
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def _get_contact_profile(db: AsyncSession, contact_qiao_id: str) -> Profile | None:
    """
    Get profile for a contact via qiao_id.

    Args:
        db: Database session
        contact_qiao_id: Contact's qiao_id

    Returns:
        Profile object or None if not found
    """
    return await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=contact_qiao_id)


def _build_profile_summary(
    profile: Profile | None, *, avatar_url: str | None = None
) -> ContactProfileSummary:
    """Convert Profile ORM object to API summary payload."""

    return ContactProfileSummary(
        nickname=profile.nickname if profile else None,
        avatar_url=avatar_url,
        gender=profile.gender if profile else None,
        bio=profile.bio if profile else None,
        region=profile.region if profile else None,
    )


def _extract_tags(tags: Any | None) -> list[str]:
    """Normalize stored tag payload to a list."""

    if not tags:
        return []

    if isinstance(tags, dict):
        raw = tags.get("tags")
        if isinstance(raw, list):
            return [str(tag) for tag in raw if isinstance(tag, str)]
    elif isinstance(tags, list):
        return [str(tag) for tag in tags if isinstance(tag, str)]

    return []


def _serialize_tags(tags: list[str] | None) -> dict[str, Any] | None:
    """Convert outbound tag list to storage format."""

    if tags is None:
        return None
    return {"tags": tags}


def _build_contact_list_item(
    contact: Contact, profile: Profile | None, *, avatar_url: str | None = None
) -> ContactListItem:
    """Construct a ContactListItem from ORM entities."""

    return ContactListItem(
        conversation_id=contact.conversation_id,
        contact_qiao_id=contact.contact_qiao_id,
        alias=contact.alias,
        tags=_extract_tags(contact.tags),
        is_pinned=bool(contact.is_pinned),
        is_muted=bool(contact.is_muted),
        is_blocked=bool(contact.is_blocked),
        profile=_build_profile_summary(profile, avatar_url=avatar_url),
    )


def _build_contact_detail(
    contact: Contact, profile: Profile | None, *, avatar_url: str | None = None
) -> ContactDetailResponse:
    """Construct a ContactDetailResponse."""

    list_item = _build_contact_list_item(contact, profile, avatar_url=avatar_url)
    return ContactDetailResponse(**list_item.model_dump(), remark=contact.remark)


async def get_user_contacts_with_profiles(
    db: AsyncSession,
    user_qiao_id: str,
    contact_type: ContactType | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ContactListItem], bool]:
    """
    Get user's contacts with profile information and IM conversation ID.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        contact_type: Optional filter by contact type
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        Tuple of (contacts, has_more)
    """
    # Get contacts from database
    contacts = await contact_crud.get_user_contacts(
        db,
        user_qiao_id=user_qiao_id,
        contact_type=contact_type,
        include_blocked=False,
        skip=skip,
        limit=limit + 1,
    )

    has_more = len(contacts) > limit
    contacts = contacts[:limit]

    # Load profiles and batch-generate avatar URLs
    profile_cache: dict[int, Profile | None] = {}
    profiles_with_avatars: list[Profile] = []
    for contact in contacts:
        profile = await _get_contact_profile(db, contact.contact_qiao_id)
        profile_cache[contact.id] = profile
        if profile:
            profiles_with_avatars.append(profile)

    avatar_urls = await get_avatar_urls_batch(profiles_with_avatars)

    # Build response list
    result = []
    for contact in contacts:
        profile = profile_cache.get(contact.id)
        avatar_url = avatar_urls.get(profile.id) if profile else None
        contact_response = _build_contact_list_item(contact, profile, avatar_url=avatar_url)
        result.append(contact_response)

    logger.info(
        "contacts_retrieved",
        user_qiao_id=user_qiao_id,
        count=len(result),
        contact_type=contact_type,
    )

    return result, has_more


async def get_contact_with_profile(
    db: AsyncSession, user_qiao_id: str, conversation_id: str
) -> ContactDetailResponse | None:
    """
    Get specific contact with profile information and IM conversation ID.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conversation_id: Conversation identifier

    Returns:
        ContactDetailResponse or None if not found
    """
    # Get contact from database
    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conversation_id)

    if not contact:
        logger.warning("contact_not_found", conversation_id=conversation_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conversation_id=conversation_id,
        )
        return None

    # Get profile
    profile = await _get_contact_profile(db, contact.contact_qiao_id)

    avatar_url = await get_avatar_url(profile)

    # Build response
    contact_response = _build_contact_detail(contact, profile, avatar_url=avatar_url)

    logger.info("contact_retrieved", user_qiao_id=user_qiao_id, conversation_id=conversation_id)

    return contact_response


async def update_contact(
    db: AsyncSession, user_qiao_id: str, conversation_id: str, update_data: ContactUpdate
) -> ContactDetailResponse | None:
    """
    Update contact information.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conversation_id: Conversation identifier
        update_data: Contact update data

    Returns:
        Updated ContactResponse or None if not found

    Raises:
        ValueError: If validation fails
    """
    # Get contact
    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conversation_id)

    if not contact:
        logger.warning("contact_not_found_for_update", conversation_id=conversation_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_update_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conversation_id=conversation_id,
        )
        return None

    # Prepare update dict.
    # Use model_fields_set to distinguish "field omitted" from "explicit null".
    provided_fields = update_data.model_fields_set
    update_dict: dict[str, Any] = {}
    if "alias" in provided_fields:
        update_dict["alias"] = update_data.alias
    if "tags" in provided_fields:
        update_dict["tags"] = _serialize_tags(update_data.tags)
    if "remark" in provided_fields:
        update_dict["remark"] = update_data.remark
    if update_data.is_pinned is not None:
        update_dict["is_pinned"] = 1 if update_data.is_pinned else 0
    if update_data.is_muted is not None:
        update_dict["is_muted"] = 1 if update_data.is_muted else 0

    # Update contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in=update_dict)

    # Get profile
    profile = await _get_contact_profile(db, updated_contact.contact_qiao_id)

    avatar_url = await get_avatar_url(profile)

    # Build response
    contact_response = _build_contact_detail(updated_contact, profile, avatar_url=avatar_url)

    logger.info(
        "contact_updated",
        user_qiao_id=user_qiao_id,
        conversation_id=conversation_id,
        updated_fields=list(update_dict.keys()),
    )

    return contact_response


async def block_contact(
    db: AsyncSession, user_qiao_id: str, conversation_id: str
) -> ContactDetailResponse | None:
    """
    Block a contact.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conversation_id: Conversation identifier

    Returns:
        Updated ContactResponse or None if not found
    """
    # Get contact
    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conversation_id)

    if not contact:
        logger.warning("contact_not_found_for_block", conversation_id=conversation_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_block_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conversation_id=conversation_id,
        )
        return None

    # Block contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in={"is_blocked": 1})

    # Get profile
    profile = await _get_contact_profile(db, updated_contact.contact_qiao_id)

    avatar_url = await get_avatar_url(profile)

    # Build response
    contact_response = _build_contact_detail(updated_contact, profile, avatar_url=avatar_url)

    logger.info("contact_blocked", user_qiao_id=user_qiao_id, conversation_id=conversation_id)

    return contact_response


async def unblock_contact(
    db: AsyncSession, user_qiao_id: str, conversation_id: str
) -> ContactDetailResponse | None:
    """
    Unblock a contact.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conversation_id: Conversation identifier

    Returns:
        Updated ContactResponse or None if not found
    """
    # Get contact
    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conversation_id)

    if not contact:
        logger.warning("contact_not_found_for_unblock", conversation_id=conversation_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_unblock_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conversation_id=conversation_id,
        )
        return None

    # Unblock contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in={"is_blocked": 0})

    # Get profile
    profile = await _get_contact_profile(db, updated_contact.contact_qiao_id)

    avatar_url = await get_avatar_url(profile)

    # Build response
    contact_response = _build_contact_detail(updated_contact, profile, avatar_url=avatar_url)

    logger.info("contact_unblocked", user_qiao_id=user_qiao_id, conversation_id=conversation_id)

    return contact_response


async def delete_contact(db: AsyncSession, user_qiao_id: str, conversation_id: str) -> bool:
    """
    Delete a contact (soft delete).

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conversation_id: Conversation identifier

    Returns:
        True if deleted successfully, False if not found or access denied
    """
    # Get contact
    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conversation_id)

    if not contact:
        logger.warning("contact_not_found_for_delete", conversation_id=conversation_id)
        return False

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_delete_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conversation_id=conversation_id,
        )
        return False

    # Soft delete contact
    await contact_crud.soft_delete_contact(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=contact.contact_qiao_id
    )

    logger.info("contact_deleted", user_qiao_id=user_qiao_id, conversation_id=conversation_id)

    return True
