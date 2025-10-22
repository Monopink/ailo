"""
Account security API endpoints.

This module provides account security management endpoints including:
- Password management (change, reset)
- Email management (bind, change, unbind)
- Phone number management (change)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.deps import get_current_user
from models.user import User
from crud.user import user as user_crud
from schemas.password import ChangePasswordRequest, ResetPasswordRequest
from schemas.email_manage import (
    EmailSendCodeRequest,
    EmailSendCodeResponse,
    BindEmailRequest,
    BindEmailResponse,
    ChangeEmailRequest,
    ChangeEmailResponse,
    UnbindEmailRequest,
)
from schemas.phone_manage import ChangePhoneRequest, ChangePhoneResponse
from core.security import verify_password, get_password_hash
from utils.logging import get_logger
from utils.phone import normalize_phone, mask_phone
from utils.email import validate_email, mask_email

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["Account Security"])


# Import operation token functions from auth module
from api.v1.auth import _verify_operation_token


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user password.

    For first-time password setup, old_password is optional.
    For password change, old_password is required.

    Args:
        body: Password change request
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Check if user has password
        has_password = bool(current_user.password_hash)

        if has_password:
            # User has password, must verify old password
            if not body.old_password:
                raise HTTPException(status_code=400, detail="请输入当前密码")

            if not verify_password(body.old_password, current_user.password_hash):
                raise HTTPException(status_code=400, detail="当前密码错误")

        # Set new password
        new_password_hash = get_password_hash(body.new_password)
        await user_crud.update(db, db_obj=current_user, obj_in={"password_hash": new_password_hash})

        logger.info("password_changed", user_id=current_user.id, first_time=not has_password)

    except HTTPException:
        raise

    except Exception as e:
        logger.error("change_password_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="修改密码失败，请稍后再试")


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset user password using operation token.

    Does not require login. Used for forgot password scenario.

    Args:
        body: Password reset request
        db: Database session

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Verify operation token
        user_id = _verify_operation_token(body.operation_token)
        if not user_id:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        # Get user
        user = await user_crud.get(db, id=user_id)
        if not user:
            raise HTTPException(status_code=400, detail="用户不存在")

        # Set new password
        new_password_hash = get_password_hash(body.new_password)
        await user_crud.update(db, db_obj=user, obj_in={"password_hash": new_password_hash})

        logger.info("password_reset", user_id=user_id)

    except HTTPException:
        raise

    except Exception as e:
        logger.error("reset_password_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="重置密码失败，请稍后再试")


@router.post("/email/send-code", response_model=EmailSendCodeResponse)
async def send_email_code(
    body: EmailSendCodeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send verification code to email.

    Used for binding or changing email.

    Args:
        body: Email send code request
        current_user: Current authenticated user

    Returns:
        EmailSendCodeResponse: Cooldown time

    Raises:
        HTTPException: 400/501 for various errors
    """
    try:
        # Validate email
        if not validate_email(body.email):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")

        # TODO: Implement email verification code sending
        raise HTTPException(status_code=501, detail="邮箱验证功能暂未实现")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("send_email_code_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="发送验证码失败，请稍后再试")


@router.post("/email", response_model=BindEmailResponse)
async def bind_email(
    body: BindEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bind email to user account.

    Args:
        body: Bind email request
        current_user: Current authenticated user
        db: Database session

    Returns:
        BindEmailResponse: Masked email

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Validate email
        if not validate_email(body.email):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")

        # Check if email already bound
        if current_user.email:
            raise HTTPException(status_code=400, detail="已绑定邮箱，请先解绑")

        # Check if email already used by another user
        existing_user = await user_crud.get_by_email(db, email=body.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="该邮箱已被使用")

        # TODO: Verify email code
        # For now, skip verification

        # Bind email
        await user_crud.update(db, db_obj=current_user, obj_in={"email": body.email})

        logger.info("email_bound", user_id=current_user.id, email=body.email)

        return BindEmailResponse(email=mask_email(body.email))

    except HTTPException:
        raise

    except Exception as e:
        logger.error("bind_email_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="绑定邮箱失败，请稍后再试")


@router.put("/email", response_model=ChangeEmailResponse)
async def change_email(
    body: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user email.

    Requires operation token for verification.

    Args:
        body: Change email request
        current_user: Current authenticated user
        db: Database session

    Returns:
        ChangeEmailResponse: Masked new email

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Verify operation token
        user_id = _verify_operation_token(body.operation_token)
        if not user_id or user_id != current_user.id:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        # Validate email
        if not validate_email(body.new_email):
            raise HTTPException(status_code=400, detail="邮箱格式不正确")

        # Check if email already used by another user
        existing_user = await user_crud.get_by_email(db, email=body.new_email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=400, detail="该邮箱已被使用")

        # TODO: Verify email code
        # For now, skip verification

        # Change email
        await user_crud.update(db, db_obj=current_user, obj_in={"email": body.new_email})

        logger.info("email_changed", user_id=current_user.id, new_email=body.new_email)

        return ChangeEmailResponse(email=mask_email(body.new_email))

    except HTTPException:
        raise

    except Exception as e:
        logger.error("change_email_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="修改邮箱失败，请稍后再试")


@router.delete("/email", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_email(
    body: UnbindEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unbind email from user account.

    Requires operation token for verification.

    Args:
        body: Unbind email request
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Verify operation token
        user_id = _verify_operation_token(body.operation_token)
        if not user_id or user_id != current_user.id:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        # Check if email is bound
        if not current_user.email:
            raise HTTPException(status_code=400, detail="未绑定邮箱")

        # Unbind email
        await user_crud.update(db, db_obj=current_user, obj_in={"email": None})

        logger.info("email_unbound", user_id=current_user.id)

    except HTTPException:
        raise

    except Exception as e:
        logger.error("unbind_email_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="解绑邮箱失败，请稍后再试")


@router.put("/phone", response_model=ChangePhoneResponse)
async def change_phone(
    body: ChangePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change user phone number.

    Requires operation token for verification and SMS code for new phone.

    Args:
        body: Change phone request
        current_user: Current authenticated user
        db: Database session

    Returns:
        ChangePhoneResponse: Masked new phone number

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Verify operation token
        user_id = _verify_operation_token(body.operation_token)
        if not user_id or user_id != current_user.id:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        # Normalize new phone
        normalized_phone = normalize_phone(body.new_phone)

        # Check if phone already used by another user
        existing_user = await user_crud.get_by_phone(db, phone=normalized_phone)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=400, detail="该手机号已被使用")

        # TODO: Verify SMS code for new phone
        # For now, skip verification

        # Change phone
        await user_crud.update(db, db_obj=current_user, obj_in={"phone": normalized_phone})

        logger.info("phone_changed", user_id=current_user.id, new_phone=normalized_phone)

        return ChangePhoneResponse(phone=mask_phone(normalized_phone))

    except HTTPException:
        raise

    except Exception as e:
        logger.error("change_phone_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="修改手机号失败，请稍后再试")
