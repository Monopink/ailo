"""
Contact service business logic.

This module provides business logic for contact management operations.
"""

from typing import List, Optional

from crud.contact import contact as contact_crud
from crud.profile import profile as profile_crud
from crud.system import system_configs
from enums import ContactType, ProfileOwnerType
from models.contact import Contact
from models.profile import Profile
from schemas.contact import (
    ContactInfoBase,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    ConversationInfoResponse,
)
from services.message.providers.leancloud.service import ensure_system_conversation
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


async def _get_im_conv_id(db: AsyncSession, ensure_valid: bool = False) -> str:
    """
    Get IM provider conversation ID from system config.

    Args:
        db: Database session
        ensure_valid: Whether to validate the stored ID against LeanCloud

    Returns:
        IM conversation ID

    Raises:
        ValueError: If conversation ID is not configured
    """
    conv_id = await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
    if ensure_valid or not conv_id:
        conv_id = await ensure_system_conversation(db, existing_conv_id=conv_id)

    if not conv_id:
        logger.error("im_conv_id_not_configured")
        raise ValueError("IM conversation ID not configured in system settings")

    return conv_id


async def _get_contact_profile(
    db: AsyncSession, contact_qiao_id: str, contact_type: ContactType
) -> Optional[Profile]:
    """
    Get profile for a contact.

    Args:
        db: Database session
        contact_qiao_id: Contact's qiao_id
        contact_type: Contact type

    Returns:
        Profile object or None if not found
    """
    # Map ContactType to ProfileOwnerType
    owner_type_map = {
        ContactType.USER: ProfileOwnerType.USER,
        ContactType.AI: ProfileOwnerType.AI_INSTANCE,
        ContactType.OFFICIAL: ProfileOwnerType.USER,  # Official accounts use USER type
    }

    owner_type = owner_type_map.get(contact_type)
    if not owner_type:
        logger.warning("unknown_contact_type", contact_type=contact_type)
        return None

    return await profile_crud.get_by_owner_qiao_id(db, owner_qiao_id=contact_qiao_id, owner_type=owner_type)


def _build_contact_list_response(
    contact: Contact, im_conv_id: str, profile: Optional[Profile] = None
) -> ContactListResponse:
    """
    Build ContactListResponse from contact and profile data.

    Args:
        contact: Contact model instance
        im_conv_id: IM provider conversation ID
        profile: Optional profile data

    Returns:
        ContactListResponse instance
    """
    return ContactListResponse(
        conv_id=contact.conv_id,
        im_conv_id=im_conv_id,
        contact_qiao_id=contact.contact_qiao_id,
        contact_type=ContactType(contact.contact_type),
        alias=contact.alias,
        custom_avatar_url=contact.custom_avatar_url,
        is_pinned=bool(contact.is_pinned),
        is_muted=bool(contact.is_muted),
        is_blocked=bool(contact.is_blocked),
        source=contact.source,
        created_at=contact.created_at,
        # Add profile fields
        nickname=profile.nickname if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        bio=profile.bio if profile else None,
        gender=profile.gender if profile else None,
    )


def _build_contact_response(
    contact: Contact, im_conv_id: str, profile: Optional[Profile] = None
) -> ContactResponse:
    """
    Build ContactResponse from contact and profile data.

    Args:
        contact: Contact model instance
        im_conv_id: IM provider conversation ID
        profile: Optional profile data

    Returns:
        ContactResponse instance
    """
    return ContactResponse(
        conv_id=contact.conv_id,
        im_conv_id=im_conv_id,
        contact_id=contact.id,
        contact_type=ContactType(contact.contact_type),
        contact_qiao_id=contact.contact_qiao_id,
        alias=contact.alias,
        custom_avatar_url=contact.custom_avatar_url,
        tags=contact.tags,
        remark=contact.remark,
        is_pinned=bool(contact.is_pinned),
        is_muted=bool(contact.is_muted),
        is_blocked=bool(contact.is_blocked),
        is_deleted=bool(contact.is_deleted),
        source=contact.source,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


async def get_user_contacts_with_profiles(
    db: AsyncSession,
    user_qiao_id: str,
    contact_type: Optional[ContactType] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[ContactListResponse]:
    """
    Get user's contacts with profile information and IM conversation ID.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        contact_type: Optional filter by contact type
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of ContactListResponse with im_conv_id populated
    """
    # Get IM conversation ID (validated for detail view)
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contacts from database
    contacts = await contact_crud.get_user_contacts(
        db,
        user_qiao_id=user_qiao_id,
        contact_type=contact_type,
        include_blocked=False,
        skip=skip,
        limit=limit,
    )

    # Build response list
    result = []
    for contact in contacts:
        # Get profile for additional info (optional, for future use)
        profile = await _get_contact_profile(db, contact.contact_qiao_id, ContactType(contact.contact_type))

        # Build response
        contact_response = _build_contact_list_response(contact, im_conv_id, profile)
        result.append(contact_response)

    logger.info(
        "contacts_retrieved",
        user_qiao_id=user_qiao_id,
        count=len(result),
        contact_type=contact_type,
    )

    return result


async def get_contact_with_profile(
    db: AsyncSession, user_qiao_id: str, conv_id: str
) -> Optional[ContactResponse]:
    """
    Get specific contact with profile information and IM conversation ID.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID

    Returns:
        ContactResponse with im_conv_id or None if not found
    """
    # Get IM conversation ID (force validation for conversation entry)
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contact from database
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("contact_not_found", conv_id=conv_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return None

    # Get profile
    profile = await _get_contact_profile(db, contact.contact_qiao_id, ContactType(contact.contact_type))

    # Build response
    contact_response = _build_contact_response(contact, im_conv_id, profile)

    logger.info("contact_retrieved", user_qiao_id=user_qiao_id, conv_id=conv_id)

    return contact_response


async def get_conversation_info(
    db: AsyncSession, user_qiao_id: str, conv_id: str
) -> Optional[ConversationInfoResponse]:
    """
    Get conversation information including contact basic info and IM conversation ID.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID

    Returns:
        ConversationInfoResponse or None if not found
    """
    # Get IM conversation ID
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contact
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("conversation_not_found", conv_id=conv_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "conversation_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return None

    # Get profile
    profile = await _get_contact_profile(db, contact.contact_qiao_id, ContactType(contact.contact_type))

    # Build contact info
    contact_info = ContactInfoBase(
        nickname=profile.nickname if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        gender=profile.gender if profile else None,
    )

    # Build response
    response = ConversationInfoResponse(
        conv_id=contact.conv_id,
        im_conv_id=im_conv_id,
        contact_qiao_id=contact.contact_qiao_id,
        contact_type=ContactType(contact.contact_type),
        contact_info=contact_info,
    )

    logger.info("conversation_info_retrieved", user_qiao_id=user_qiao_id, conv_id=conv_id)

    return response


async def update_contact(
    db: AsyncSession, user_qiao_id: str, conv_id: str, update_data: ContactUpdate
) -> Optional[ContactResponse]:
    """
    Update contact information.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID
        update_data: Contact update data

    Returns:
        Updated ContactResponse or None if not found

    Raises:
        ValueError: If validation fails
    """
    # Get IM conversation ID
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contact
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("contact_not_found_for_update", conv_id=conv_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_update_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return None

    # Prepare update dict (only include non-None values)
    update_dict = {}
    if update_data.alias is not None:
        update_dict["alias"] = update_data.alias
    if update_data.custom_avatar_url is not None:
        update_dict["custom_avatar_url"] = update_data.custom_avatar_url
    if update_data.tags is not None:
        update_dict["tags"] = update_data.tags
    if update_data.remark is not None:
        update_dict["remark"] = update_data.remark
    if update_data.is_pinned is not None:
        update_dict["is_pinned"] = 1 if update_data.is_pinned else 0
    if update_data.is_muted is not None:
        update_dict["is_muted"] = 1 if update_data.is_muted else 0
    if update_data.is_blocked is not None:
        update_dict["is_blocked"] = 1 if update_data.is_blocked else 0

    # Update contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in=update_dict)

    # Get profile
    profile = await _get_contact_profile(
        db, updated_contact.contact_qiao_id, ContactType(updated_contact.contact_type)
    )

    # Build response
    contact_response = _build_contact_response(updated_contact, im_conv_id, profile)

    logger.info(
        "contact_updated",
        user_qiao_id=user_qiao_id,
        conv_id=conv_id,
        updated_fields=list(update_dict.keys()),
    )

    return contact_response


async def block_contact(db: AsyncSession, user_qiao_id: str, conv_id: str) -> Optional[ContactResponse]:
    """
    Block a contact.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID

    Returns:
        Updated ContactResponse or None if not found
    """
    # Get IM conversation ID
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contact
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("contact_not_found_for_block", conv_id=conv_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_block_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return None

    # Block contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in={"is_blocked": 1})

    # Get profile
    profile = await _get_contact_profile(
        db, updated_contact.contact_qiao_id, ContactType(updated_contact.contact_type)
    )

    # Build response
    contact_response = _build_contact_response(updated_contact, im_conv_id, profile)

    logger.info("contact_blocked", user_qiao_id=user_qiao_id, conv_id=conv_id)

    return contact_response


async def unblock_contact(db: AsyncSession, user_qiao_id: str, conv_id: str) -> Optional[ContactResponse]:
    """
    Unblock a contact.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID

    Returns:
        Updated ContactResponse or None if not found
    """
    # Get IM conversation ID
    im_conv_id = await _get_im_conv_id(db, ensure_valid=True)

    # Get contact
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("contact_not_found_for_unblock", conv_id=conv_id)
        return None

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_unblock_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return None

    # Unblock contact
    updated_contact = await contact_crud.update(db, db_obj=contact, obj_in={"is_blocked": 0})

    # Get profile
    profile = await _get_contact_profile(
        db, updated_contact.contact_qiao_id, ContactType(updated_contact.contact_type)
    )

    # Build response
    contact_response = _build_contact_response(updated_contact, im_conv_id, profile)

    logger.info("contact_unblocked", user_qiao_id=user_qiao_id, conv_id=conv_id)

    return contact_response


async def delete_contact(db: AsyncSession, user_qiao_id: str, conv_id: str) -> bool:
    """
    Delete a contact (soft delete).

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        conv_id: Conversation ID

    Returns:
        True if deleted successfully, False if not found or access denied
    """
    # Get contact
    contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)

    if not contact:
        logger.warning("contact_not_found_for_delete", conv_id=conv_id)
        return False

    # Verify ownership
    if contact.user_qiao_id != user_qiao_id:
        logger.warning(
            "contact_delete_access_denied",
            user_qiao_id=user_qiao_id,
            contact_owner=contact.user_qiao_id,
            conv_id=conv_id,
        )
        return False

    # Soft delete contact
    await contact_crud.soft_delete_contact(
        db, user_qiao_id=user_qiao_id, contact_qiao_id=contact.contact_qiao_id
    )

    logger.info("contact_deleted", user_qiao_id=user_qiao_id, conv_id=conv_id)

    return True
