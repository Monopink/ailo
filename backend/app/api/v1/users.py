"""User profile API endpoints.

This module provides user profile management endpoints including:
- Get user profile
- Update user profile
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.message import media_file as media_file_crud
from app.crud.profile import profile as profile_crud
from app.crud.user import user as user_crud
from app.enums import FileStatus, ProfileOwnerType
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.schemas.user_profile import (
    UserAccountResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.profile.avatar import get_avatar_url
from app.utils.email import mask_email
from app.utils.logging import get_logger
from app.utils.phone import mask_phone

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["User Profile"])


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """Get current user's profile.

    Returns only profile data (from profiles table).
    Does not include account security information (phone, email, etc).
    avatar_url is dynamically generated from avatar_key.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserProfileResponse: User profile data with dynamically generated avatar_url

    """
    try:
        # Get user profile
        user_profile = await profile_crud.get_by_owner(
            db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER
        )

        # Generate avatar URL dynamically
        avatar_url = await get_avatar_url(user_profile)

        # Build response
        response = UserProfileResponse(
            qiao_id=current_user.qiao_id,
            username=current_user.username,
            nickname=user_profile.nickname if user_profile else None,
            gender=user_profile.gender if user_profile else None,
            avatar_url=avatar_url,
            bio=user_profile.bio if user_profile else None,
            region=user_profile.region if user_profile else None,
        )

        logger.info("user_profile_retrieved", qiao_id=current_user.qiao_id)

        return response

    except Exception as e:
        logger.error(
            "get_user_profile_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="获取用户资料失败，请稍后再试") from e


@router.get("/account", response_model=UserAccountResponse)
async def get_user_account(
    current_user: User = Depends(get_current_user),
) -> UserAccountResponse:
    """Get current user's account information.

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
        logger.error(
            "get_user_account_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="获取账户信息失败，请稍后再试") from e


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    body: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Update current user's profile.

    All fields are optional. Only provided fields will be updated.
    avatar_file_id must reference an existing media_files record owned by the current user.
    It will be converted to avatar_key (object key) and avatar_media_id (audit FK).

    Args:
        body: Profile update data (avatar_file_id in file_xxx format)
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserProfileResponse: Updated user profile data with dynamically generated avatar_url

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

        # Validate avatar_file_id if provided
        avatar_key = None
        avatar_media_id = None
        if body.avatar_file_id is not None:
            # Get media file by file_id (file_xxx format)
            media_file = await media_file_crud.get_by_file_id(db, file_id=body.avatar_file_id)
            if not media_file:
                raise HTTPException(status_code=404, detail="头像文件不存在")

            # Verify ownership
            if media_file.upload_by_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权操作")

            # Verify file status
            if media_file.status != int(FileStatus.ACTIVE):
                raise HTTPException(status_code=400, detail="头像文件未激活")

            # Set both avatar_key (for URL generation) and avatar_media_id (for audit)
            avatar_key = media_file.object_key
            avatar_media_id = media_file.id

        # Check if profile exists
        user_profile = await profile_crud.get_by_owner(
            db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER
        )

        # Prepare update data (exclude username as it's not a profile field)
        profile_data = body.model_dump(exclude_unset=True, exclude={"username"})

        # Convert avatar_file_id from file_xxx to both avatar_key and avatar_media_id
        if "avatar_file_id" in profile_data:
            profile_data["avatar_key"] = avatar_key
            profile_data["avatar_media_id"] = avatar_media_id
            del profile_data["avatar_file_id"]  # Remove old field

        update_data = ProfileUpdate(**profile_data)

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
            updated_profile = await profile_crud.create_with_owner(
                db,
                obj_in=create_data,
                owner_id=current_user.id,
                owner_qiao_id=current_user.qiao_id,
                owner_type=ProfileOwnerType.USER,
            )

        # Generate avatar URL dynamically
        avatar_url = await get_avatar_url(updated_profile)

        if current_user.needs_profile_setup:
            current_user = await user_crud.update(
                db, db_obj=current_user, obj_in={"needs_profile_setup": False}
            )
            logger.info("needs_profile_setup_cleared", qiao_id=current_user.qiao_id)

        # Build response
        response = UserProfileResponse(
            qiao_id=current_user.qiao_id,
            username=current_user.username,
            nickname=updated_profile.nickname,
            gender=updated_profile.gender,
            avatar_url=avatar_url,
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
