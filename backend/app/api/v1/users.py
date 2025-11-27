"""
User profile API endpoints.

This module provides user profile management endpoints including:
- Get user profile
- Update user profile
"""

from api.deps import get_current_user
from core.database import get_db
from crud.profile import profile as profile_crud
from crud.user import user as user_crud
from enums import ProfileOwnerType
from fastapi import APIRouter, Depends, HTTPException
from models.user import User
from schemas.profile import ProfileCreate, ProfileUpdate
from schemas.user_profile import UserAccountResponse, UserProfileResponse, UserProfileUpdateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from utils.email import mask_email
from utils.logging import get_logger
from utils.phone import mask_phone

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["User Profile"])


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get current user's profile.

    Returns only profile data (from profiles table).
    Does not include account security information (phone, email, etc).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserProfileResponse: User profile data
    """
    try:
        # Get user profile
        user_profile = await profile_crud.get_by_owner(
            db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER
        )

        # Build response
        response = UserProfileResponse(
            qiao_id=current_user.qiao_id,
            username=current_user.username,
            nickname=user_profile.nickname if user_profile else None,
            gender=user_profile.gender if user_profile else None,
            avatar_url=user_profile.avatar_url if user_profile else None,
            bio=user_profile.bio if user_profile else None,
            region=user_profile.region if user_profile else None,
        )

        logger.info("user_profile_retrieved", qiao_id=current_user.qiao_id)

        return response

    except Exception as e:
        logger.error("get_user_profile_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True)
        raise HTTPException(status_code=500, detail="获取用户资料失败，请稍后再试") from e


@router.get("/account", response_model=UserAccountResponse)
async def get_user_account(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's account information.

    Returns account security related information including:
    - qiao_id, username
    - Masked phone number
    - Masked email (if bound)
    - Password status

    Args:
        current_user: Current authenticated user

    Returns:
        UserAccountResponse: User account data
    """
    try:
        # Mask phone number
        masked_phone = mask_phone(current_user.phone) if current_user.phone else ""

        # Mask email
        masked_email = mask_email(current_user.email) if current_user.email else None

        # Check if user has password
        has_password = bool(current_user.password_hash)

        # Build response
        response = UserAccountResponse(
            qiao_id=current_user.qiao_id,
            username=current_user.username,
            phone=masked_phone,
            email=masked_email,
            has_password=has_password,
        )

        logger.info("user_account_retrieved", qiao_id=current_user.qiao_id)

        return response

    except Exception as e:
        logger.error("get_user_account_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True)
        raise HTTPException(status_code=500, detail="获取账户信息失败，请稍后再试") from e


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    body: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user's profile.

    All fields are optional. Only provided fields will be updated.
    If avatar_url starts with "assets://", avatar_prompt will be automatically set.

    Args:
        body: Profile update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserProfileResponse: Updated user profile data
    """
    try:
        # Update username if provided (user table field)
        if body.username is not None:
            # Check if username already exists
            existing_user = await user_crud.get_by_username(db, username=body.username)
            if existing_user and existing_user.id != current_user.id:
                raise HTTPException(status_code=400, detail="该用户名已被使用")

            # Update username
            await user_crud.update(db, db_obj=current_user, obj_in={"username": body.username})
            current_user.username = body.username  # Update local object

        # Check if profile exists
        user_profile = await profile_crud.get_by_owner(
            db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER
        )

        # Prepare update data (exclude username as it's not a profile field)
        profile_data = body.model_dump(exclude_unset=True, exclude={"username"})
        update_data = ProfileUpdate(**profile_data)

        # Handle avatar_prompt for assets:// URLs
        if body.avatar_url and body.avatar_url.startswith("assets://"):
            update_data.avatar_prompt = body.avatar_url

        if user_profile:
            # Update existing profile
            updated_profile = await profile_crud.update_by_owner(
                db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER, obj_in=update_data
            )
            if not updated_profile:
                raise HTTPException(status_code=500, detail="更新用户资料失败，请稍后再试")
        else:
            # Create new profile
            create_data = ProfileCreate(**profile_data)
            if body.avatar_url and body.avatar_url.startswith("assets://"):
                create_data.avatar_prompt = body.avatar_url

            updated_profile = await profile_crud.create_with_owner(
                db,
                obj_in=create_data,
                owner_id=current_user.id,
                owner_qiao_id=current_user.qiao_id,
                owner_type=ProfileOwnerType.USER,
            )

        # Build response
        response = UserProfileResponse(
            qiao_id=current_user.qiao_id,
            username=current_user.username,
            nickname=updated_profile.nickname,
            gender=updated_profile.gender,
            avatar_url=updated_profile.avatar_url,
            bio=updated_profile.bio,
            region=updated_profile.region,
        )

        logger.info("user_profile_updated", qiao_id=current_user.qiao_id)

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "update_user_profile_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="更新用户资料失败，请稍后再试") from e
