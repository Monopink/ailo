from fastapi import APIRouter, Depends

from app import models, schemas  # type: ignore
from app.api import deps  # type: ignore

router = APIRouter()


@router.get("/me")
async def read_current_user(
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Get current user information.
    Returns user data with entity_id mapped to id for frontend.
    """
    return {
        "id": current_user.entity_id,  # entity_id mapped to id for frontend
        "phone": current_user.phone,
        "username": current_user.username,
        "email": current_user.email,
        "status": current_user.status,
        "role": current_user.role,
        "is_verified": current_user.is_verified,
        "subscription_type": current_user.subscription_type,
        "contact_limit": current_user.contact_limit,  # Contact limit for frontend display
    }
