"""
Authentication API endpoints.

This module provides authentication-related endpoints including:
- SMS verification code sending
- User registration
- User login (SMS-based)
- Message client signature generation for LeanCloud IM authentication
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Dict, Tuple

from core.database import get_db
from services.message.providers.leancloud.signature import create_login_signature
from services.security.sms.factory import create_sms_provider
from services.security.rate_limiter import check_rate_limit
from crud.system import system_configs
from crud.user import user as user_crud, user_token as token_crud
from models.user import User, UserToken
from enums import DeviceType
from utils.logging import get_logger
from utils.token import generate_jwt_token, calculate_token_expiry
from models.base import generate_qiao_id
from services.wechat.client import WeChatClient, WeChatAPIError
from services.wechat import code_manager
from utils.phone import normalize_phone, is_china_phone
from schemas.auth import (
    WeChatLoginRequest,
    WeChatLoginResponse,
    BindPhoneRequest,
    BindPhoneResponse,
    VerifyPhoneRequest,
    VerifyPhoneResponse,
    CompleteRegistrationRequest,
    CompleteRegistrationResponse,
)
from schemas.verify import (
    VerifySendCodeRequest,
    VerifySendCodeResponse,
    VerifyConfirmRequest,
    OperationTokenResponse,
)
from api.deps import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory verification code storage (for MVP)
# Format: phone -> (code, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verification_codes: Dict[str, Tuple[str, datetime]] = {}

# In-memory verified phone token storage (for MVP)
# Format: token -> (phone, wechat_openid, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verified_phone_tokens: Dict[str, Tuple[str, str | None, datetime]] = {}

# In-memory operation token storage (for MVP)
# Format: token -> (user_id, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_operation_tokens: Dict[str, Tuple[int, datetime]] = {}


def _cleanup_expired_codes() -> None:
    """
    Clean up expired verification codes from memory.

    This function should be called before storing new codes to prevent memory leaks.
    In production, Redis TTL should be used instead.
    """
    now = datetime.utcnow()
    expired_phones = [phone for phone, (_, expires_at) in _verification_codes.items() if now >= expires_at]
    for phone in expired_phones:
        del _verification_codes[phone]

    if expired_phones:
        logger.info("verification_codes_cleaned", count=len(expired_phones))


def _cleanup_expired_phone_tokens() -> None:
    """
    Clean up expired verified phone tokens from memory.

    This function should be called before storing new tokens to prevent memory leaks.
    In production, Redis TTL should be used instead.
    """
    now = datetime.utcnow()
    expired_tokens = [
        token for token, (_, _, expires_at) in _verified_phone_tokens.items() if now >= expires_at
    ]
    for token in expired_tokens:
        del _verified_phone_tokens[token]

    if expired_tokens:
        logger.info("verified_phone_tokens_cleaned", count=len(expired_tokens))


def _cleanup_expired_operation_tokens() -> None:
    """
    Clean up expired operation tokens from memory.

    This function should be called before storing new tokens to prevent memory leaks.
    In production, Redis TTL should be used instead.
    """
    now = datetime.utcnow()
    expired_tokens = [token for token, (_, expires_at) in _operation_tokens.items() if now >= expires_at]
    for token in expired_tokens:
        del _operation_tokens[token]

    if expired_tokens:
        logger.info("operation_tokens_cleaned", count=len(expired_tokens))


def _generate_operation_token(user_id: int) -> str:
    """
    Generate an operation token for sensitive operations.

    Args:
        user_id: User ID

    Returns:
        Operation token string
    """
    import secrets

    token = f"opt_{secrets.token_urlsafe(32)}"
    expires_at = datetime.utcnow() + timedelta(minutes=5)  # 5 minutes expiration
    _operation_tokens[token] = (user_id, expires_at)
    _cleanup_expired_operation_tokens()  # Clean up expired tokens

    logger.info("operation_token_generated", user_id=user_id)

    return token


def _verify_operation_token(token: str) -> int | None:
    """
    Verify operation token and return user ID.

    Args:
        token: Operation token

    Returns:
        User ID if valid, None if invalid or expired
    """
    if token not in _operation_tokens:
        logger.warning("operation_token_not_found", token=token[:10])
        return None

    user_id, expires_at = _operation_tokens[token]
    if datetime.utcnow() >= expires_at:
        del _operation_tokens[token]
        logger.warning("operation_token_expired", token=token[:10])
        return None

    return user_id


def _generate_verified_phone_token(phone: str, wechat_openid: str | None = None) -> str:
    """
    Generate a temporary verified phone token for new user registration.

    Args:
        phone: Verified phone number
        wechat_openid: Optional WeChat openid to bind

    Returns:
        Temporary token string
    """
    import secrets

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=5)  # 5 minutes expiration
    _verified_phone_tokens[token] = (phone, wechat_openid, expires_at)
    _cleanup_expired_phone_tokens()  # Clean up expired tokens

    logger.info("verified_phone_token_generated", phone=phone, expires_at=expires_at)
    return token


def _verify_phone_token(token: str) -> tuple[str, str | None] | None:
    """
    Verify and consume a verified phone token.

    Args:
        token: Temporary token to verify

    Returns:
        Tuple of (phone, wechat_openid) if valid, None if invalid or expired
    """
    _cleanup_expired_phone_tokens()  # Clean up expired tokens first

    stored_data = _verified_phone_tokens.get(token)
    if not stored_data:
        return None

    phone, wechat_openid, expires_at = stored_data
    if datetime.utcnow() >= expires_at:
        del _verified_phone_tokens[token]
        return None

    # Token is valid, remove it (one-time use)
    del _verified_phone_tokens[token]
    return phone, wechat_openid


class SendSMSRequest(BaseModel):
    """Request model for sending SMS verification code"""

    phone: str = Field(..., description="Phone number (11 digits)")


class SendSMSResponse(BaseModel):
    """Response model for sending SMS"""

    message: str


class MessageClientSignatureRequest(BaseModel):
    """Request model for message client signature"""

    client_id: str


class MessageClientSignatureResponse(BaseModel):
    """Response model for message client signature"""

    signature: str
    timestamp: int
    nonce: str
    client_id: str


@router.post("/send-sms", response_model=SendSMSResponse)
async def send_sms_code(request: Request, body: SendSMSRequest, db: AsyncSession = Depends(get_db)):
    """
    Send SMS verification code.

    Args:
        request: FastAPI request
        body: Contains phone number
        db: Database session

    Returns:
        SendSMSResponse with success message

    Raises:
        HTTPException: 400 for invalid phone, 429 for rate limit
    """
    # Normalize and check phone number
    try:
        normalized_phone = normalize_phone(body.phone)

        # Check if China phone
        if not is_china_phone(normalized_phone):
            logger.warning("sms_send_not_china_phone", phone=normalized_phone)
            raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")

    except ValueError as e:
        logger.error("sms_send_invalid_phone_format", phone=body.phone, error=str(e))
        raise HTTPException(status_code=400, detail="手机号格式无效")

    # Check SMS rate limit
    allowed, error_code, retry_after = await check_rate_limit(normalized_phone, "sms", db)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": error_code,
                "message": "短信发送过于频繁，请稍后再试",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Generate 6-digit verification code
    import random

    code = "".join([str(random.randint(0, 9)) for _ in range(6)])

    # Store code in memory with expiration (for MVP)
    # In production, use Redis with TTL instead
    expires_at = datetime.utcnow() + timedelta(minutes=5)  # 5 minutes expiration
    _verification_codes[normalized_phone] = (code, expires_at)
    _cleanup_expired_codes()  # Clean up expired codes

    # Send SMS
    provider = await create_sms_provider(db)
    result = await provider.send_verification_code(normalized_phone, code)

    if not result.success:
        logger.error(
            "sms_send_failed",
            phone=normalized_phone,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        raise HTTPException(status_code=500, detail="短信发送失败，请稍后再试")

    logger.info("sms_sent", phone=normalized_phone, provider_id=result.provider_id)

    return SendSMSResponse(message="验证码已发送")


@router.post("/message-client", response_model=MessageClientSignatureResponse)
async def get_message_client_signature(
    request: MessageClientSignatureRequest, db: AsyncSession = Depends(get_db)
):
    """
    Generate authentication signature for message client.

    This endpoint generates an HMAC-SHA1 signature that allows the client
    to authenticate with the messaging service (LeanCloud IM).

    The signature is generated using:
    - App ID from system configuration
    - Master Key from environment variables
    - Client ID from request
    - Current timestamp and random nonce

    Security:
    - TODO: Add user authentication when user API is implemented
    - Currently allows any client_id for MVP development
    - Master Key is never exposed to client

    Args:
        request: Contains client_id (user's qiao_id)
        db: Database session

    Returns:
        MessageClientSignatureResponse containing:
        - signature: HMAC-SHA1 signature hex string
        - timestamp: UTC timestamp in milliseconds
        - nonce: Random nonce string
        - client_id: Echo back the client_id

    Raises:
        HTTPException: 500 if LeanCloud configuration is missing
    """
    try:
        # Get LeanCloud app_id from system_configs
        app_id = await system_configs.get_config_value(db, config_key="leancloud_app_id")

        if not app_id:
            logger.error("leancloud_app_id_not_configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Message service not configured",
            )

        # Generate signature
        signature_data = await create_login_signature(app_id=app_id, client_id=request.client_id)

        logger.info(
            "message_client_signature_generated",
            client_id=request.client_id,
            timestamp=signature_data["timestamp"],
        )

        return MessageClientSignatureResponse(
            signature=signature_data["signature"],
            timestamp=signature_data["timestamp"],
            nonce=signature_data["nonce"],
            client_id=request.client_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "message_client_signature_generation_failed", error=str(e), client_id=request.client_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate signature",
        )


@router.post("/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(request: Request, body: WeChatLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    WeChat Mini Program login

    Args:
        request: FastAPI request
        body: Contains login_code and phone_code
        db: Database session

    Returns:
        WeChatLoginResponse with user info or phone binding requirement

    Raises:
        HTTPException: 400/500 for various errors
    """
    client_ip = request.client.host
    wechat_client = WeChatClient()

    try:
        # 1. Get access_token
        access_token = await wechat_client.get_access_token()

        # 2. Exchange login_code for openid
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]

        logger.info("wechat_login_code2session_success", openid=openid[:8] + "...", ip=client_ip)

        # 3. Exchange phone_code for phone number
        phone_data = await wechat_client.get_phone_number(body.phone_code, access_token)
        phone_info = phone_data.get("phone_info", {})

        country_code = phone_info.get("countryCode")
        pure_phone = phone_info.get("purePhoneNumber")

        logger.info(
            "wechat_phone_obtained",
            openid=openid[:8] + "...",
            country_code=country_code,
            phone=pure_phone,
            ip=client_ip,
        )

        # 4. Check country code
        if country_code != 86:
            # International phone, need SMS binding
            logger.warning(
                "wechat_international_phone",
                openid=openid[:8] + "...",
                country_code=country_code,
                ip=client_ip,
            )

            # Generate temporary code for phone binding
            wechat_code = code_manager.generate_code(openid)

            return WeChatLoginResponse(
                success=False,
                needs_phone_binding=True,
                wechat_code=wechat_code,
                message="请绑定中国大陆手机号",
            )

        # 5. Normalize phone number
        try:
            # Construct E.164 format phone
            phone_e164 = f"+{country_code}{pure_phone}"
            normalized_phone = normalize_phone(phone_e164)

            logger.info(
                "wechat_phone_normalized",
                openid=openid[:8] + "...",
                phone=normalized_phone,
                ip=client_ip,
            )

        except ValueError as e:
            # Invalid phone format, need SMS binding
            logger.warning(
                "wechat_invalid_phone_format",
                openid=openid[:8] + "...",
                phone=pure_phone,
                error=str(e),
                ip=client_ip,
            )

            # Generate temporary code for phone binding
            wechat_code = code_manager.generate_code(openid)

            return WeChatLoginResponse(
                success=False,
                needs_phone_binding=True,
                wechat_code=wechat_code,
                message="手机号格式无效,请绑定手机号",
            )

        # 6. Find or create user
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        if not user:
            # Create new user
            try:
                from utils.snowflake import generate_snowflake_id

                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    wechat_openid=openid,
                    username=f"用户{qiao_id[-6:]}",
                    user_type=1,  # Normal user
                    status=1,  # Active
                )

                db.add(user)
                await db.commit()
                await db.refresh(user)

                logger.info(
                    "wechat_user_created",
                    qiao_id=qiao_id,
                    openid=openid[:8] + "...",
                    phone=normalized_phone,
                    ip=client_ip,
                )

            except Exception as e:
                logger.error(
                    "wechat_user_creation_failed",
                    openid=openid[:8] + "...",
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail="用户创建失败")
        else:
            # Update wechat_openid if not set
            if not user.wechat_openid:
                user.wechat_openid = openid
                await db.commit()
                await db.refresh(user)

                logger.info(
                    "wechat_openid_updated",
                    qiao_id=user.qiao_id,
                    openid=openid[:8] + "...",
                    ip=client_ip,
                )

        # 7. Check user status
        if not await user_crud.is_active(user):
            logger.warning("wechat_login_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        # 8. Create token
        try:
            from utils.snowflake import generate_snowflake_id

            jwt_token = generate_jwt_token(
                user_id=user.id, qiao_id=user.qiao_id, device_type=DeviceType.MINI_PROGRAM
            )
            expires_at = calculate_token_expiry()

            user_token = UserToken(
                id=generate_snowflake_id(),
                user_id=user.id,
                user_qiao_id=user.qiao_id,
                token=jwt_token,
                device_type=DeviceType.MINI_PROGRAM,
                device_id=None,
                platform_info=None,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                expires_at=expires_at,
                status=1,  # Active
            )

            db.add(user_token)
            await db.commit()
            await db.refresh(user_token)

            logger.info(
                "wechat_token_created",
                qiao_id=user.qiao_id,
                token=jwt_token[:16] + "...",
            )

        except Exception as e:
            logger.error(
                "wechat_token_creation_failed",
                qiao_id=user.qiao_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="登录失败")

        # 9. Get user profile
        from models.profile import Profile
        from enums import ProfileOwnerType
        from sqlalchemy import select

        profile_result = await db.execute(
            select(Profile).where(Profile.owner_id == user.id, Profile.owner_type == ProfileOwnerType.USER)
        )
        profile = profile_result.scalar_one_or_none()

        # 10. Return response
        return WeChatLoginResponse(
            success=True,
            needs_phone_binding=False,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "nickname": profile.nickname if profile else None,
                "gender": profile.gender if profile else 0,
                "avatar_url": profile.avatar_url if profile else None,
                "bio": profile.bio if profile else None,
                "token": jwt_token,
            },
            message="登录成功",
        )

    except WeChatAPIError as e:
        logger.error(
            "wechat_api_error",
            errcode=e.errcode,
            errmsg=e.errmsg,
            ip=client_ip,
        )
        raise HTTPException(status_code=500, detail="微信服务异常,请稍后再试")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("wechat_login_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="登录失败,请稍后再试")


@router.post("/bind-phone", response_model=BindPhoneResponse)
async def bind_phone(request: Request, body: BindPhoneRequest, db: AsyncSession = Depends(get_db)):
    """
    Bind phone number via SMS verification
    This endpoint is used when WeChat returns international phone or invalid phone format.
    User needs to bind a China mainland phone number via SMS verification.

    Args:
        request: FastAPI request
        body: Contains wechat_code, phone, and sms_code
        db: Database session

    Returns:
        BindPhoneResponse with user info

    Raises:
        HTTPException: 400/500 for various errors
    """
    client_ip = request.client.host

    try:
        # 1. Normalize phone number first
        try:
            normalized_phone = normalize_phone(body.phone)

            # Check if China phone
            if not is_china_phone(normalized_phone):
                logger.warning("bind_phone_not_china_phone", phone=normalized_phone, ip=client_ip)
                raise HTTPException(status_code=400, detail="请使用中国大陆手机号")

        except ValueError as e:
            logger.error("bind_phone_invalid_phone_format", phone=body.phone, error=str(e), ip=client_ip)
            raise HTTPException(status_code=400, detail="手机号格式无效")

        # 2. Verify wechat_code
        openid = code_manager.verify_code(body.wechat_code)
        if not openid:
            logger.warning(
                "bind_phone_invalid_wechat_code", code=body.wechat_code[:8] + "...", ip=client_ip
            )
            raise HTTPException(status_code=400, detail="验证码无效或已过期")

        logger.info("bind_phone_wechat_code_verified", openid=openid[:8] + "...", ip=client_ip)

        # 3. Verify SMS code (use normalized_phone)
        stored_data = _verification_codes.get(normalized_phone)
        if not stored_data:
            logger.warning("bind_phone_sms_code_not_found", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="短信验证码错误或已过期")

        stored_code, expires_at = stored_data
        if datetime.utcnow() >= expires_at:
            logger.warning("bind_phone_sms_code_expired", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="短信验证码已过期")

        if stored_code != body.sms_code:
            logger.warning("bind_phone_sms_code_mismatch", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="短信验证码错误")

        logger.info(
            "bind_phone_phone_verified", openid=openid[:8] + "...", phone=normalized_phone, ip=client_ip
        )

        # 4. Find or create user
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        if not user:
            # Create new user
            try:
                from utils.snowflake import generate_snowflake_id

                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    wechat_openid=openid,
                    username=f"用户{qiao_id[-6:]}",
                    user_type=1,  # Normal user
                    status=1,  # Active
                )

                db.add(user)
                await db.commit()
                await db.refresh(user)

                logger.info(
                    "bind_phone_user_created",
                    qiao_id=qiao_id,
                    openid=openid[:8] + "...",
                    phone=normalized_phone,
                    ip=client_ip,
                )

            except Exception as e:
                logger.error(
                    "bind_phone_user_creation_failed",
                    openid=openid[:8] + "...",
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail="用户创建失败")
        else:
            # Update wechat_openid if not set
            if not user.wechat_openid:
                user.wechat_openid = openid
                await db.commit()
                await db.refresh(user)

                logger.info(
                    "bind_phone_openid_updated",
                    qiao_id=user.qiao_id,
                    openid=openid[:8] + "...",
                    ip=client_ip,
                )

        # 5. Check user status
        if not await user_crud.is_active(user):
            logger.warning("bind_phone_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        # 6. Create token
        try:
            from utils.snowflake import generate_snowflake_id

            jwt_token = generate_jwt_token(
                user_id=user.id, qiao_id=user.qiao_id, device_type=DeviceType.MINI_PROGRAM
            )
            expires_at = calculate_token_expiry()

            user_token = UserToken(
                id=generate_snowflake_id(),
                user_id=user.id,
                user_qiao_id=user.qiao_id,
                token=jwt_token,
                device_type=DeviceType.MINI_PROGRAM,
                device_id=None,
                platform_info=None,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                expires_at=expires_at,
                status=1,  # Active
            )

            db.add(user_token)
            await db.commit()
            await db.refresh(user_token)

            logger.info(
                "bind_phone_token_created",
                qiao_id=user.qiao_id,
                token=jwt_token[:16] + "...",
            )

        except Exception as e:
            logger.error(
                "bind_phone_token_creation_failed",
                qiao_id=user.qiao_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="绑定失败")

        # 7. Clear verification code
        _verification_codes.pop(body.phone, None)

        # 8. Return response
        return BindPhoneResponse(
            success=True,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "username": user.username,
                "token": jwt_token,
            },
            message="绑定成功",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("bind_phone_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="绑定失败,请稍后再试")


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """
    User logout endpoint.

    Revokes the current JWT token by marking it as inactive in the database.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        dict: Success response

    Raises:
        HTTPException: 401 if not authenticated or token invalid
    """
    from api.deps import get_current_user

    client_ip = request.client.host

    # 1. Get current user (validates token)
    user = await get_current_user(request, db)

    # 2. Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    token = auth_header[7:]  # Remove "Bearer " prefix

    # 3. Revoke token
    try:
        revoked_token = await token_crud.revoke_token(db, token=token)
        if not revoked_token:
            logger.warning("logout_token_not_found", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=401, detail="登录失效")

        logger.info("user_logged_out", qiao_id=user.qiao_id, ip=client_ip)

        return {"success": True}

    except HTTPException:
        raise

    except Exception as e:
        logger.error("logout_failed", error=str(e), qiao_id=user.qiao_id, ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="退出登录失败，请稍后再试")


@router.post("/phone", response_model=VerifyPhoneResponse)
async def verify_phone(request: Request, body: VerifyPhoneRequest, db: AsyncSession = Depends(get_db)):
    """
    Unified phone verification endpoint (login/registration entry).
    This endpoint handles both login and registration scenarios:
    - If user exists: Direct login, return token and user info
    - If user doesn't exist: Return temporary token for profile setup

    Args:
        request: FastAPI request
        body: Contains phone, sms_code, and optional wechat_code
        db: Database session

    Returns:
        VerifyPhoneResponse with login info or registration token

    Raises:
        HTTPException: 400/500 for various errors
    """
    client_ip = request.client.host

    try:
        # 1. Normalize phone number
        try:
            normalized_phone = normalize_phone(body.phone)

            # Check if China phone
            if not is_china_phone(normalized_phone):
                logger.warning("verify_phone_not_china_phone", phone=normalized_phone, ip=client_ip)
                raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")

        except ValueError as e:
            logger.error("verify_phone_invalid_phone_format", phone=body.phone, error=str(e), ip=client_ip)
            raise HTTPException(status_code=400, detail="手机号格式无效")

        # 2. Verify SMS code
        stored_data = _verification_codes.get(normalized_phone)
        if not stored_data:
            logger.warning("verify_phone_sms_code_not_found", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        stored_code, expires_at = stored_data
        if datetime.utcnow() >= expires_at:
            logger.warning("verify_phone_sms_code_expired", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="验证码已过期")

        if stored_code != body.sms_code:
            logger.warning("verify_phone_sms_code_mismatch", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="验证码错误")

        logger.info("verify_phone_sms_verified", phone=normalized_phone, ip=client_ip)

        # 3. Get WeChat openid if wechat_code provided
        wechat_openid = None
        if body.wechat_code:
            wechat_openid = code_manager.verify_code(body.wechat_code)
            if not wechat_openid:
                logger.warning(
                    "verify_phone_invalid_wechat_code",
                    code=body.wechat_code[:8] + "...",
                    ip=client_ip,
                )
                raise HTTPException(status_code=400, detail="微信验证码无效或已过期")

            logger.info("verify_phone_wechat_code_verified", openid=wechat_openid[:8] + "...", ip=client_ip)

        # 4. Check if user exists
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        if user:
            # User exists - direct login
            logger.info(
                "verify_phone_user_exists", qiao_id=user.qiao_id, phone=normalized_phone, ip=client_ip
            )

            # Bind WeChat openid if provided and not already bound
            if wechat_openid and not user.wechat_openid:
                user.wechat_openid = wechat_openid
                await db.commit()
                await db.refresh(user)

                logger.info(
                    "verify_phone_wechat_bound",
                    qiao_id=user.qiao_id,
                    openid=wechat_openid[:8] + "...",
                    ip=client_ip,
                )

            # Check user status
            if not await user_crud.is_active(user):
                logger.warning("verify_phone_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
                raise HTTPException(status_code=400, detail="账号已被禁用")

            # Create token
            try:
                from utils.snowflake import generate_snowflake_id

                jwt_token = generate_jwt_token(
                    user_id=user.id,
                    qiao_id=user.qiao_id,
                    device_type=DeviceType.MINI_PROGRAM,
                )
                expires_at = calculate_token_expiry()

                user_token = UserToken(
                    id=generate_snowflake_id(),
                    user_id=user.id,
                    user_qiao_id=user.qiao_id,
                    token=jwt_token,
                    device_type=DeviceType.MINI_PROGRAM,
                    device_id=None,
                    platform_info=None,
                    ip_address=client_ip,
                    user_agent=request.headers.get("user-agent"),
                    expires_at=expires_at,
                    status=1,  # Active
                )

                db.add(user_token)
                await db.commit()
                await db.refresh(user_token)

                logger.info(
                    "verify_phone_token_created",
                    qiao_id=user.qiao_id,
                    token=jwt_token[:16] + "...",
                )

            except Exception as e:
                logger.error(
                    "verify_phone_token_creation_failed",
                    qiao_id=user.qiao_id,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail="登录失败，请稍后再试")

            # Clear verification code
            _verification_codes.pop(normalized_phone, None)

            # Get user profile
            from models.profile import Profile
            from enums import ProfileOwnerType
            from sqlalchemy import select

            profile_result = await db.execute(
                select(Profile).where(
                    Profile.owner_id == user.id, Profile.owner_type == ProfileOwnerType.USER
                )
            )
            profile = profile_result.scalar_one_or_none()

            # Return login response
            return VerifyPhoneResponse(
                is_new_user=False,
                token=jwt_token,
                user={
                    "qiao_id": user.qiao_id,
                    "phone": user.phone,
                    "nickname": profile.nickname if profile else None,
                    "gender": profile.gender if profile else 0,
                    "avatar_url": profile.avatar_url if profile else None,
                    "bio": profile.bio if profile else None,
                },
            )

        else:
            # User doesn't exist - return temporary token for registration
            logger.info("verify_phone_new_user", phone=normalized_phone, ip=client_ip)

            # Generate temporary token
            verified_phone_token = _generate_verified_phone_token(normalized_phone, wechat_openid)

            # Clear verification code
            _verification_codes.pop(normalized_phone, None)

            # Return registration token
            return VerifyPhoneResponse(
                is_new_user=True,
                verified_phone_token=verified_phone_token,
                phone=normalized_phone,
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("verify_phone_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="验证失败，请稍后再试")


@router.post("/complete-registration", response_model=CompleteRegistrationResponse)
async def complete_registration(
    request: Request, body: CompleteRegistrationRequest, db: AsyncSession = Depends(get_db)
):
    """
    Complete user registration with profile information.
    This endpoint is called after phone verification for new users.
    It creates the user account with the provided profile information.

    Args:
        request: FastAPI request
        body: Contains verified_phone_token and profile information
        db: Database session

    Returns:
        CompleteRegistrationResponse with token and user info

    Raises:
        HTTPException: 400/500 for various errors
    """
    client_ip = request.client.host

    try:
        # 1. Verify temporary token
        token_data = _verify_phone_token(body.verified_phone_token)
        if not token_data:
            logger.warning(
                "complete_registration_invalid_token",
                token=body.verified_phone_token[:16] + "...",
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="操作超时，请重试")

        phone, wechat_openid = token_data
        logger.info("complete_registration_token_verified", phone=phone, ip=client_ip)

        # 2. Check if user already exists (防止重复创建)
        existing_user = await user_crud.get_by_phone(db, phone=phone)
        if existing_user:
            logger.warning(
                "complete_registration_user_exists",
                phone=phone,
                qiao_id=existing_user.qiao_id,
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="该手机号已注册")

        # 3. Create user and profile
        try:
            from utils.snowflake import generate_snowflake_id
            from models.profile import Profile
            from enums import ProfileOwnerType

            user_id = generate_snowflake_id()
            qiao_id = generate_qiao_id()

            # Create user (account info only)
            user = User(
                id=user_id,
                qiao_id=qiao_id,
                phone=phone,
                wechat_openid=wechat_openid,
                username=f"用户{qiao_id[-6:]}",  # Default username
                user_type=1,  # Normal user
                status=1,  # Active
            )

            db.add(user)
            await db.flush()  # Flush to get user.id

            # Create profile (personal info)
            profile = Profile(
                id=generate_snowflake_id(),
                owner_id=user.id,
                owner_qiao_id=user.qiao_id,
                owner_type=ProfileOwnerType.USER,
                nickname=body.nickname,
                gender=body.gender if body.gender is not None else 0,  # Default to unknown
                bio=body.bio,
                avatar_url=body.avatar_url,
            )

            db.add(profile)
            await db.commit()
            await db.refresh(user)
            await db.refresh(profile)

            logger.info(
                "complete_registration_user_created",
                qiao_id=qiao_id,
                phone=phone,
                nickname=body.nickname,
                ip=client_ip,
            )

        except Exception as e:
            logger.error(
                "complete_registration_user_creation_failed",
                phone=phone,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="注册失败，请稍后再试")

        # 4. Create token
        try:
            from utils.snowflake import generate_snowflake_id

            jwt_token = generate_jwt_token(
                user_id=user.id,
                qiao_id=user.qiao_id,
                device_type=DeviceType.MINI_PROGRAM,
            )
            expires_at = calculate_token_expiry()

            user_token = UserToken(
                id=generate_snowflake_id(),
                user_id=user.id,
                user_qiao_id=user.qiao_id,
                token=jwt_token,
                device_type=DeviceType.MINI_PROGRAM,
                device_id=None,
                platform_info=None,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                expires_at=expires_at,
                status=1,  # Active
            )

            db.add(user_token)
            await db.commit()
            await db.refresh(user_token)

            logger.info(
                "complete_registration_token_created",
                qiao_id=user.qiao_id,
                token=jwt_token[:16] + "...",
            )

        except Exception as e:
            logger.error(
                "complete_registration_token_creation_failed",
                qiao_id=user.qiao_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="注册失败，请稍后再试")

        # 5. Return response
        return CompleteRegistrationResponse(
            token=jwt_token,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "nickname": profile.nickname,
                "gender": profile.gender,
                "avatar_url": profile.avatar_url,
                "bio": profile.bio,
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("complete_registration_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试")


# ============================================================================
# Unified Verification Mechanism
# ============================================================================


@router.post("/user/verify/send-code", response_model=VerifySendCodeResponse)
async def send_verification_code(
    body: VerifySendCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send verification code for unified verification mechanism.

    Supports phone and email verification.
    Used for sensitive operations like changing phone/email, resetting password, etc.

    Args:
        body: Verification code request
        current_user: Current authenticated user
        db: Database session

    Returns:
        VerifySendCodeResponse: Cooldown time

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        # Determine target
        if body.verify_type == "phone":
            target = body.target if body.target else current_user.phone
            if not target:
                raise HTTPException(status_code=400, detail="用户未绑定手机号")

            # Normalize phone
            normalized_phone = normalize_phone(target)

            # Check rate limit
            check_rate_limit(f"sms:{normalized_phone}", max_requests=5, window_seconds=3600)

            # Generate verification code
            import random

            code = f"{random.randint(100000, 999999)}"

            # Store code
            expires_at = datetime.utcnow() + timedelta(minutes=5)
            _verification_codes[normalized_phone] = (code, expires_at)
            _cleanup_expired_codes()

            # Send SMS
            sms_provider = create_sms_provider()
            await sms_provider.send_verification_code(normalized_phone, code)

            logger.info("verification_code_sent", phone=normalized_phone, user_id=current_user.id)

            return VerifySendCodeResponse(cooldown=60)

        elif body.verify_type == "email":
            target = body.target if body.target else current_user.email
            if not target:
                raise HTTPException(status_code=400, detail="用户未绑定邮箱")

            # TODO: Implement email verification code sending
            # For now, raise not implemented error
            raise HTTPException(status_code=501, detail="邮箱验证功能暂未实现")

        else:
            raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("send_verification_code_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="发送验证码失败，请稍后再试")


@router.post("/user/verify/confirm", response_model=OperationTokenResponse)
async def confirm_verification_code(
    body: VerifyConfirmRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Confirm verification code and get operation token.

    Args:
        body: Verification confirmation request
        current_user: Current authenticated user

    Returns:
        OperationTokenResponse: Operation token and expiration time

    Raises:
        HTTPException: 400/500 for various errors
    """
    try:
        if body.verify_type == "phone":
            # Get user's phone
            if not current_user.phone:
                raise HTTPException(status_code=400, detail="用户未绑定手机号")

            normalized_phone = normalize_phone(current_user.phone)

            # Verify code
            if normalized_phone not in _verification_codes:
                raise HTTPException(status_code=400, detail="验证码不存在或已过期")

            stored_code, expires_at = _verification_codes[normalized_phone]

            if datetime.utcnow() >= expires_at:
                del _verification_codes[normalized_phone]
                raise HTTPException(status_code=400, detail="验证码已过期")

            if stored_code != body.code:
                raise HTTPException(status_code=400, detail="验证码错误")

            # Delete used code
            del _verification_codes[normalized_phone]

            # Generate operation token
            operation_token = _generate_operation_token(current_user.id)

            logger.info("verification_confirmed", user_id=current_user.id, verify_type="phone")

            return OperationTokenResponse(operation_token=operation_token, expires_in=300)

        elif body.verify_type == "email":
            # TODO: Implement email verification
            raise HTTPException(status_code=501, detail="邮箱验证功能暂未实现")

        else:
            raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("confirm_verification_failed", error=str(e), user_id=current_user.id, exc_info=True)
        raise HTTPException(status_code=500, detail="验证失败，请稍后再试")
