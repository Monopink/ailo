import re
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models
from app.api import deps
from app.core import security
from app.core.sms import send_sms_code, verify_sms_code
from app.models import user as user_model
from app.schemas.user import (
    User,
    UserCreate,
    Token,
    PhoneSchema,
    UserLoginPassword,
    UserLoginCode,
    PasswordReset,
)

router = APIRouter()


@router.post("/send-code", summary="发送短信验证码 (Send SMS Code)")
async def request_sms_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    phone_data: PhoneSchema = Body(...),
):
    """
    Sends a verification code to a user's phone number.
    In this mock version, the code is printed to the console.
    """
    phone = phone_data.phone
    # Basic validation for Chinese phone numbers
    if not re.match(r"^1[3-9]\d{9}$", phone):
        raise HTTPException(status_code=400, detail="请输入有效的11位手机号码。")

    user = await crud.user.get_user_by_phone(db, phone=phone)
    if user:
        # If it's a password reset or code login request, the user must exist.
        # If it's a registration request, a new user will be created.
        # We can send the code in either case.
        pass

    send_sms_code(phone=phone)
    return {"msg": "SMS code sent successfully."}


@router.post("/register", response_model=User, summary="手机号密码注册 (Register with Phone and Password)")
async def register_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate,
):
    """
    Register a new user with phone, password, and verification code.
    """
    if not verify_sms_code(phone=user_in.phone, code=user_in.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取。")

    user = await crud.user.get_user_by_phone(db, phone=user_in.phone)
    if user:
        raise HTTPException(status_code=400, detail="该手机号码已被注册。")

    user = await crud.user.create_user(db=db, user_in=user_in)
    return user


@router.post(
    "/login/password", response_model=Token, summary="手机号密码登录 (Login with Phone and Password)"
)
async def login_with_password(
    db: AsyncSession = Depends(deps.get_db),
    login_data: UserLoginPassword = Body(...),
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = await crud.user.get_user_by_phone(db, phone=login_data.phone)
    if not user or not security.verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="手机号或密码不正确。")

    access_token = security.create_access_token(subject=user.entity_id, entity_id=user.entity_id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/code", response_model=Token, summary="手机号验证码登录 (Login with Phone and Code)")
async def login_with_code(
    db: AsyncSession = Depends(deps.get_db),
    login_data: UserLoginCode = Body(...),
):
    """
    Login with a phone number and a one-time verification code.
    """
    if not verify_sms_code(phone=login_data.phone, code=login_data.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取。")

    user = await crud.user.get_user_by_phone(db, phone=login_data.phone)
    if not user:
        raise HTTPException(status_code=404, detail="该手机号尚未注册。")

    access_token = security.create_access_token(subject=user.entity_id, entity_id=user.entity_id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/reset-password", summary="密码重置 (Reset Password)")
async def reset_user_password(
    db: AsyncSession = Depends(deps.get_db),
    password_data: PasswordReset = Body(...),
):
    """
    Reset password with a phone number and a verification code.
    """
    if not verify_sms_code(phone=password_data.phone, code=password_data.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取。")

    user = await crud.user.get_user_by_phone(db, phone=password_data.phone)
    if not user:
        raise HTTPException(status_code=404, detail="该手机号尚未注册。")

    await crud.user.update_password(db=db, user=user, new_password=password_data.new_password)
    return {"msg": "Password updated successfully."}


@router.get("/me", response_model=User, summary="获取当前用户信息 (Get Current User)")
async def read_users_me(
    current_user: user_model.User = Depends(deps.get_current_user),
):
    """
    Get current user's profile information.
    """
    return current_user
