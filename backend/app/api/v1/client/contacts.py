"""
Contact and social profile related API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.deps import get_current_user, get_db
from services.contacts.contacts import (
    get_user_contacts,
    search_contacts,
    get_contact_by_entity_id,
    get_contact_chat_info,
    add_contact,
)
from repositories.profile import ProfileRepository
from services.contacts.utils.contact_limits import get_user_contact_limits
from schemas.social_profile import SocialProfileCreate, SocialProfileUpdate
from models.user import User
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Initialize repository
profile_repository = ProfileRepository()


@router.get("")
async def get_contacts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get current user's contacts with their social profiles
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        contact_list = await get_user_contacts(db, user_entity_id)
        return {"status": "success", "data": contact_list}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contacts_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_contacts_endpoint(
    query: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Search available contacts from preset configuration
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")

        # Basic input validation for search query
        if len(query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        if len(query) > 100:  # Reasonable limit for search queries
            raise HTTPException(status_code=400, detail="Query too long (max 100 characters)")

        available_contacts = await search_contacts(db, user_entity_id, query)
        return {"status": "success", "data": available_contacts}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("search_contacts_endpoint_error", error=str(e), query=query)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits")
async def get_contact_limits(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get current user's contact limits and usage information
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        limits_info = await get_user_contact_limits(db, user_entity_id)
        return {"status": "success", "data": limits_info}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contact_limits_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contact_entity_id}")
async def get_contact(
    contact_entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific contact by entity ID
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        contact = await get_contact_by_entity_id(db, user_entity_id, contact_entity_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        return {"status": "success", "data": contact}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contact_endpoint_error", error=str(e), contact_entity_id=contact_entity_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contact_entity_id}/chat-info")
async def get_contact_chat_info_endpoint(
    contact_entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get specific contact's chat display information
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        chat_info = await get_contact_chat_info(db, user_entity_id, contact_entity_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Contact not found")

        return {"status": "success", "data": chat_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_contact_chat_info_endpoint_error", error=str(e), contact_entity_id=contact_entity_id
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/{entity_id}")
async def get_social_profile_endpoint(entity_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get social profile by entity ID
    """
    try:
        profile = await profile_repository.get_social_profile_by_entity_id(db, entity_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"status": "success", "data": profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_social_profile_endpoint_error", error=str(e), entity_id=entity_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile/me")
async def create_or_update_my_profile(
    profile_data: SocialProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update current user's social profile
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        # Convert Pydantic model to dict, excluding None values
        profile_dict = profile_data.dict(exclude_none=True)

        if not profile_dict:
            raise HTTPException(status_code=400, detail="No data provided for update")

        updated_profile = await profile_repository.create_or_update_social_profile(
            db, user_entity_id, profile_dict
        )

        return {"status": "success", "data": updated_profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_or_update_my_profile_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profile/me")
async def create_my_profile(
    profile_data: SocialProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create current user's social profile (for first-time setup)
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        # Check if profile already exists
        existing_profile = await profile_repository.get_social_profile_by_entity_id(db, user_entity_id)
        if existing_profile:
            raise HTTPException(status_code=409, detail="Profile already exists, use PUT to update")

        # Convert Pydantic model to dict
        profile_dict = profile_data.dict()

        created_profile = await profile_repository.create_or_update_social_profile(
            db, user_entity_id, profile_dict
        )

        return {"status": "success", "data": created_profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_my_profile_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_contact_endpoint(
    request_data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Add a new contact for the current user
    """
    try:
        user_entity_id = current_user.entity_id
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found")

        contact_id = request_data.get("contact_id")  # Frontend sends contact_id (entity_id from mapping)
        if not contact_id:
            raise HTTPException(status_code=400, detail="contact_id is required")

        # Ensure contact_id is valid string and not empty
        if not isinstance(contact_id, str) or not contact_id.strip():
            raise HTTPException(status_code=400, detail="contact_id must be a non-empty string")

        result = await add_contact(db, user_entity_id, contact_id)

        # Service layer now returns structured response, pass it through
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_contact_endpoint_error", error=str(e), request_data=request_data)
        # Return consistent error format
        return {"status": "error", "error_code": 1001, "message": "添加联系人失败"}
