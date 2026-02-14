"""Account security API endpoints.

This module provides account security management endpoints including:
- Password management (change, reset)
- Email management (bind, change, unbind)
- Phone number management (change)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.auth import _consume_sms_code, _verify_operation_token
from app.core.database import get_db
from app.crud.user import user as user_crud
from app.models.user import User
from app.schemas.email_manage import (
    BindEmailRequest,
    BindEmailResponse,
    ChangeEmailRequest,
    ChangeEmailResponse,
    EmailSendCodeRequest,
    EmailSendCodeResponse,
    UnbindEmailRequest,
)
from app.schemas.phone_manage import ChangePhoneRequest, ChangePhoneResponse
from app.utils.email import mask_email, validate_email
from app.utils.logging import get_logger
from app.utils.phone import mask_phone, normalize_phone

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["Account Security"])


@router.post("/email/send-code", response_model=EmailSendCodeResponse)
async def send_email_code(
    body: EmailSendCodeRequest,
    current_user: User = Depends(get_current_user),
) -> EmailSendCodeResponse:
    """Send verification code to email.

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
        raise HTTPException(status_code=501, detail="系统错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("send_email_code_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/email", response_model=BindEmailResponse)
async def bind_email(
    body: BindEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BindEmailResponse:
    """Bind email to user account.

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
        raise HTTPException(status_code=500, detail="系统错误")


@router.put("/email", response_model=ChangeEmailResponse)
async def change_email(
    body: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangeEmailResponse:
    """Change user email.

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
        raise HTTPException(status_code=500, detail="系统错误")


@router.delete("/email", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_email(
    body: UnbindEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unbind email from user account.

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
        raise HTTPException(status_code=500, detail="系统错误")


@router.put("/phone", response_model=ChangePhoneResponse)
async def change_phone(
    body: ChangePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePhoneResponse:
    """Change user phone number.

    If an operation token is provided it will be verified, otherwise the
    authenticated session is treated as sufficient authorization. The request
    still requires the SMS code flow handled by `/auth/send-sms`.

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
        if not body.operation_token:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        user_id = _verify_operation_token(body.operation_token)
        if not user_id or user_id != current_user.id:
            raise HTTPException(status_code=400, detail="验证失败，请重试")

        # Normalize new phone
        normalized_phone = normalize_phone(body.new_phone)

        # Check if phone already used by another user
        existing_user = await user_crud.get_by_phone(db, phone=normalized_phone)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=400, detail="该手机号已被使用")

        # Verify SMS code for new phone
        _consume_sms_code(normalized_phone, body.sms_code)

        # Change phone
        await user_crud.update(db, db_obj=current_user, obj_in={"phone": normalized_phone})

        logger.info(
            "phone_changed",
            user_id=current_user.id,
            new_phone=normalized_phone,
            has_operation_token=bool(body.operation_token),
        )

        return ChangePhoneResponse(phone=mask_phone(normalized_phone))

    except HTTPException:
        raise

    except Exception as e:
        logger.error("change_phone_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")
