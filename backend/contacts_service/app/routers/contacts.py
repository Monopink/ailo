"""
Contact and social profile related API routes
"""

from fastapi import APIRouter, Depends, HTTPException
from ..auth import get_current_user
from ..services.contact_service import contact_service
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("")
async def get_contacts(current_user: dict = Depends(get_current_user)):
    """
    Get current user's contacts with their social profiles
    """
    try:
        user_entity_id = current_user.get("entity_id")
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found in token")

        contact_list = await contact_service.get_user_contacts(user_entity_id)
        return {"status": "success", "data": contact_list}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contacts_endpoint_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contact_entity_id}")
async def get_contact(contact_entity_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get a specific contact by entity ID
    """
    try:
        user_entity_id = current_user.get("entity_id")
        if not user_entity_id:
            raise HTTPException(status_code=400, detail="User entity_id not found in token")

        contact = await contact_service.get_contact_by_entity_id(user_entity_id, contact_entity_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        return {"status": "success", "data": contact}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contact_endpoint_error", error=str(e), contact_entity_id=contact_entity_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/{entity_id}")
async def get_social_profile(entity_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get social profile by entity ID
    """
    try:
        profile = await contact_service.get_social_profile_by_entity_id(entity_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"status": "success", "data": profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_social_profile_endpoint_error", error=str(e), entity_id=entity_id)
        raise HTTPException(status_code=500, detail=str(e))
