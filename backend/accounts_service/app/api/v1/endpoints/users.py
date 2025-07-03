from fastapi import APIRouter, Depends

from app import models, schemas  # type: ignore
from app.api import deps  # type: ignore

router = APIRouter()


@router.get("/me", response_model=schemas.User)
async def read_current_user(
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Get current user information.
    """
    return current_user
