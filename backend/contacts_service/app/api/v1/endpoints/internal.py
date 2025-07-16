"""
Internal API routes for service-to-service communication
These endpoints use INTERNAL_SERVICE_KEY authentication instead of JWT
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from ..services.contacts_service import contacts_service
from ..core.config import settings
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])


def verify_internal_service_key(x_internal_key: Optional[str] = Header(None)):
    """
    Verify internal service key for service-to-service communication
    
    Args:
        x_internal_key: Internal service key from header
        
    Raises:
        HTTPException: If key is invalid or missing
    """
    expected_key = getattr(settings, "INTERNAL_SERVICE_KEY", "default_internal_key_change_me")
    
    if not x_internal_key or x_internal_key != expected_key:
        logger.warning("invalid_internal_service_key_attempt", provided_key=x_internal_key[:10] if x_internal_key else None)
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Invalid or missing internal service key"
        )


@router.get("/profile/{entity_id}")
async def get_user_profile_internal(
    entity_id: str, 
    x_internal_key: Optional[str] = Header(None)
):
    """
    Get user social profile by entity ID (internal service endpoint)
    
    This endpoint is for service-to-service communication and uses
    INTERNAL_SERVICE_KEY authentication instead of JWT tokens.
    
    Args:
        entity_id: User entity ID
        x_internal_key: Internal service authentication key
        
    Returns:
        dict: User profile data
    """
    try:
        # Verify internal service authentication
        verify_internal_service_key(x_internal_key)
        
        # Get user profile
        profile = await contacts_service.get_social_profile_by_entity_id(entity_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        logger.info("internal_profile_request_success", entity_id=entity_id)
        return {"status": "success", "data": profile}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("internal_get_profile_error", error=str(e), entity_id=entity_id)
        raise HTTPException(status_code=500, detail=str(e))
