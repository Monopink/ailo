"""
Authentication API endpoints.

This module provides authentication-related endpoints including:
- SMS verification code sending
- User registration
- User login (SMS-based)
- Message client signature generation for LeanCloud IM authentication
"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.message import media_file as media_file_crud
from app.crud.system import system_configs
from app.crud.user import user as user_crud
from app.crud.user import user_auth as user_auth_crud
from app.crud.user import user_token as token_crud
from app.enums import AuthType, DeviceType, FileStatus, ProfileOwnerType
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.models.user import User, UserToken
from app.schemas.auth import (
    BindPhoneRequest,
    BindPhoneResponse,
    CompleteRegistrationRequest,
    CompleteRegistrationResponse,
    VerifyPhoneRequest,
    VerifyPhoneResponse,
    WeChatLoginRequest,
    WeChatLoginResponse,
)
from app.schemas.verify import (
    OperationTokenResponse,
    VerifyConfirmRequest,
    VerifySendCodeRequest,
    VerifySendCodeResponse,
)
from app.services.profile.avatar import get_avatar_url
from app.services.security.captcha.factory import create_captcha_provider_for_request
from app.services.security.captcha.none import NoneCaptchaProvider
from app.services.security.rate_limiter import check_rate_limit
from app.services.security.sms.factory import create_sms_provider
from app.services.wechat import code_manager
from app.services.wechat.client import WeChatAPIError, WeChatClient
from app.utils.logging import get_logger
from app.utils.phone import is_china_phone, normalize_phone
from app.utils.snowflake import generate_snowflake_id
from app.utils.token import calculate_token_expiry, generate_jwt_token

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory verification code storage (for MVP)
# Format: phone -> (code, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verification_codes: dict[str, tuple[str, datetime]] = {}

# In-memory verified phone token storage (for MVP)
# Format: token -> (phone, wechat_openid, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verified_phone_tokens: dict[str, tuple[str, str | None, datetime]] = {}

# In-memory operation token storage (for MVP)
# Format: token -> (user_id, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_operation_tokens: dict[str, tuple[int, datetime]] = {}

# Constants
SMS_CODE_TTL_SECONDS = 5 * 60  # 5 minutes
SMS_COOLDOWN_SECONDS = 60


def _get_client_ip(request: Request) -> str:
    """
    Safely get client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address or "unknown" if not available
    """
    return request.client.host if request.client else "unknown"


async def _get_jwt_expiration_seconds(db: AsyncSession) -> int:
    """Return JWT expiration duration in seconds from configuration."""

    expires_in_days = await system_configs.get_config_value(
        db, config_key="jwt_token_expires_in_days"
    )
    if expires_in_days is None:
        logger.error("jwt_expiration_config_missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统配置缺失",
        )

    return int(expires_in_days) * 86400


def _cleanup_expired_codes() -> None:
    """
    Clean up expired verification codes from memory.

    This function should be called before storing new codes to prevent memory leaks.
    In production, Redis TTL should be used instead.
    """
    now = datetime.now(UTC)
    expired_phones = [
        phone for phone, (_, expires_at) in _verification_codes.items() if now >= expires_at
    ]
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
    now = datetime.now(UTC)
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
    now = datetime.now(UTC)
    expired_tokens = [
        token for token, (_, expires_at) in _operation_tokens.items() if now >= expires_at
    ]
    for token in expired_tokens:
        del _operation_tokens[token]

    if expired_tokens:
        logger.info("operation_tokens_cleaned", count=len(expired_tokens))


def _consume_sms_code(phone: str, sms_code: str) -> None:
    """
    Validate and consume a previously issued SMS verification code.

    Args:
        phone: Normalized E.164 phone number
        sms_code: Code provided by client

    Raises:
        HTTPException: If code is missing, expired, or mismatched
    """

    stored_data = _verification_codes.get(phone)
    if not stored_data:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    stored_code, expires_at = stored_data
    if datetime.now(UTC) >= expires_at:
        del _verification_codes[phone]
        raise HTTPException(status_code=400, detail="验证码已过期")

    if stored_code != sms_code:
        raise HTTPException(status_code=400, detail="验证码错误")

    del _verification_codes[phone]


def _generate_operation_token(user_id: int) -> str:
    """
    Generate an operation token for sensitive operations.

    Args:
        user_id: User ID

    Returns:
        Operation token string
    """

    token = f"opt_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(UTC) + timedelta(seconds=SMS_CODE_TTL_SECONDS)
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
    if datetime.now(UTC) >= expires_at:
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

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=5)  # 5 minutes expiration
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
    if datetime.now(UTC) >= expires_at:
        del _verified_phone_tokens[token]
        return None

    # Token is valid, remove it (one-time use)
    del _verified_phone_tokens[token]
    return phone, wechat_openid


class SendSMSRequest(BaseModel):
    """Request model for sending SMS verification code"""

    phone: str = Field(..., description="Phone number (11 digits)")
    # Optional for on-demand verification. When CAPTCHA is enabled and
    # token is missing, API will return HTTP 428 to instruct the client
    # to perform human verification and retry with this token.
    captcha_token: str | None = Field(None, description="CAPTCHA verification token (on-demand)")


class SendSMSResponse(BaseModel):
    """Response model for sending SMS"""

    expires_in: int = Field(..., description="Verification code TTL in seconds")
    cooldown_seconds: int = Field(..., description="Cooldown before next send in seconds")


@router.post("/send-sms", response_model=SendSMSResponse)
async def send_sms_code(
    request: Request, body: SendSMSRequest, db: AsyncSession = Depends(get_db)
) -> SendSMSResponse:
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
    # 0. On-demand CAPTCHA: if enabled and missing token -> 428
    try:
        client_ip = _get_client_ip(request)
        provider = await create_captcha_provider_for_request("user", db, request)

        # If CAPTCHA is enabled, require token; otherwise skip
        if not isinstance(provider, NoneCaptchaProvider):
            if not body.captcha_token:
                # Signal client to perform CAPTCHA first
                raise HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    detail={
                        "error": "CAPTCHA_REQUIRED",
                        "provider": "aliyun",
                        "message": "需要完成人机验证后再试",
                    },
                )

            is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
            if not is_valid:
                logger.warning("sms_captcha_failed", ip=client_ip, error=error)
                raise HTTPException(status_code=400, detail="验证失败，请稍后再试")
            logger.info("sms_captcha_verified", ip=client_ip)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("sms_captcha_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="验证服务错误，请稍后再试")

    # 1. Normalize and check phone number
    try:
        normalized_phone = normalize_phone(body.phone)

        # Check if China phone
        if not is_china_phone(normalized_phone):
            logger.warning("sms_send_not_china_phone", phone=normalized_phone)
            raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")

    except ValueError as e:
        logger.error("sms_send_invalid_phone_format", phone=body.phone, error=str(e))
        raise HTTPException(status_code=400, detail="手机号格式无效")

    # 2. Check SMS rate limit
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

    # 3. Generate 6-digit verification code
    code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

    # 4. Store code in memory with expiration (for MVP)
    # In production, use Redis with TTL instead
    expires_at = datetime.now(UTC) + timedelta(minutes=5)  # 5 minutes expiration
    _verification_codes[normalized_phone] = (code, expires_at)
    _cleanup_expired_codes()  # Clean up expired codes

    # 5. Send SMS
    sms_provider = await create_sms_provider(db)
    result = await sms_provider.send_verification_code(normalized_phone, code)

    if not result.success:
        logger.error(
            "sms_send_failed",
            phone=normalized_phone,
            error_code=result.error_code,
            error_message=result.error_message,
        )
        raise HTTPException(status_code=500, detail="短信发送失败，请稍后再试")

    logger.info("sms_sent", phone=normalized_phone, provider_id=result.provider_id)

    return SendSMSResponse(expires_in=SMS_CODE_TTL_SECONDS, cooldown_seconds=SMS_COOLDOWN_SECONDS)


@router.post("/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(
    request: Request, body: WeChatLoginRequest, db: AsyncSession = Depends(get_db)
) -> WeChatLoginResponse:
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
    client_ip = _get_client_ip(request)
    wechat_client = WeChatClient()

    try:
        # 1. Get access_token
        access_token = await wechat_client.get_access_token()

        # 2. Exchange login_code for openid
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]
        unionid = session_data.get("unionid")

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

        # 4. Check if China phone by constructing E.164 format
        try:
            phone_e164 = f"+{country_code}{pure_phone}"
            if not is_china_phone(phone_e164):
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
                    user=None,
                    message="请绑定中国大陆手机号",
                )
        except Exception:
            # If phone format check fails, treat as non-China phone
            logger.warning(
                "wechat_phone_check_failed",
                openid=openid[:8] + "...",
                country_code=country_code,
                ip=client_ip,
            )
            wechat_code = code_manager.generate_code(openid)
            return WeChatLoginResponse(
                success=False,
                needs_phone_binding=True,
                wechat_code=wechat_code,
                user=None,
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
                user=None,
                message="手机号格式无效,请绑定手机号",
            )

        # 6. Find or create user
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        # If an existing binding for this openid exists and points to a different user, block login
        existing_binding = await user_auth_crud.get_by_provider_uid(
            db, auth_type=AuthType.WECHAT, provider_uid=openid
        )

        if not user:
            # Create new user
            try:
                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
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
            # If binding exists and belongs to another user -> reject
            if existing_binding and existing_binding.user_id != user.id:
                logger.warning(
                    "wechat_openid_already_bound",
                    bound_user_id=existing_binding.user_id,
                    phone=normalized_phone,
                    ip=client_ip,
                )
                raise HTTPException(status_code=409, detail="该微信已绑定其它账号")

            # Ensure binding exists
            if not existing_binding:
                try:
                    await user_auth_crud.create_binding(
                        db,
                        user_id=user.id,
                        user_qiao_id=user.qiao_id,
                        auth_type=AuthType.WECHAT,
                        provider_uid=openid,
                        unionid=unionid,
                    )
                    logger.info(
                        "wechat_binding_created", qiao_id=user.qiao_id, openid=openid[:8] + "..."
                    )
                except Exception as e:
                    logger.error("wechat_binding_create_failed", error=str(e), exc_info=True)
                    raise HTTPException(status_code=500, detail="绑定失败")

        # 7. Check user status
        if not await user_crud.is_active(user):
            logger.warning("wechat_login_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        # 8. Create token
        try:
            expires_in_seconds = await _get_jwt_expiration_seconds(db)
            jwt_token = generate_jwt_token(
                user_id=user.id,
                qiao_id=user.qiao_id,
                device_type=DeviceType.MINI_PROGRAM,
                expires_in_seconds=expires_in_seconds,
            )
            expires_at = calculate_token_expiry(expires_in_seconds)

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

        profile_result = await db.execute(
            select(Profile).where(
                Profile.owner_id == user.id, Profile.owner_type == ProfileOwnerType.USER
            )
        )
        profile = profile_result.scalar_one_or_none()
        avatar_url = await get_avatar_url(db, profile)

        # 10. Return response
        return WeChatLoginResponse(
            success=True,
            needs_phone_binding=False,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "nickname": profile.nickname if profile else None,
                "gender": profile.gender if profile else 0,
                "avatar_url": avatar_url,
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
async def bind_phone(
    request: Request, body: BindPhoneRequest, db: AsyncSession = Depends(get_db)
) -> BindPhoneResponse:
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
    client_ip = _get_client_ip(request)

    try:
        # 1. Normalize phone number first
        try:
            normalized_phone = normalize_phone(body.phone)

            # Check if China phone
            if not is_china_phone(normalized_phone):
                logger.warning("bind_phone_not_china_phone", phone=normalized_phone, ip=client_ip)
                raise HTTPException(status_code=400, detail="请使用中国大陆手机号")

        except ValueError as e:
            logger.error(
                "bind_phone_invalid_phone_format", phone=body.phone, error=str(e), ip=client_ip
            )
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
        if datetime.now(UTC) >= expires_at:
            logger.warning("bind_phone_sms_code_expired", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="短信验证码已过期")

        if stored_code != body.sms_code:
            logger.warning("bind_phone_sms_code_mismatch", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="短信验证码错误")

        logger.info(
            "bind_phone_phone_verified",
            openid=openid[:8] + "...",
            phone=normalized_phone,
            ip=client_ip,
        )

        # 4. Find or create user
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        existing_binding = await user_auth_crud.get_by_provider_uid(
            db, auth_type=AuthType.WECHAT, provider_uid=openid
        )

        if not user:
            # Create new user
            try:
                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
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
            # If binding exists and belongs to another user -> reject
            if existing_binding and existing_binding.user_id != user.id:
                logger.warning(
                    "bind_phone_wechat_already_bound",
                    bound_user_id=existing_binding.user_id,
                    phone=normalized_phone,
                    ip=client_ip,
                )
                raise HTTPException(status_code=409, detail="该微信已绑定其它账号")

            # Ensure binding exists
            if not existing_binding:
                # Cannot get unionid here without login_code; leave unionid None
                unionid = None

                await user_auth_crud.create_binding(
                    db,
                    user_id=user.id,
                    user_qiao_id=user.qiao_id,
                    auth_type=AuthType.WECHAT,
                    provider_uid=openid,
                    unionid=unionid,
                )
                logger.info(
                    "bind_phone_binding_created", qiao_id=user.qiao_id, openid=openid[:8] + "..."
                )

        # 5. Check user status
        if not await user_crud.is_active(user):
            logger.warning("bind_phone_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        # 6. Create token
        try:
            expires_in_seconds = await _get_jwt_expiration_seconds(db)
            jwt_token = generate_jwt_token(
                user_id=user.id,
                qiao_id=user.qiao_id,
                device_type=DeviceType.MINI_PROGRAM,
                expires_in_seconds=expires_in_seconds,
            )
            expires_at = calculate_token_expiry(expires_in_seconds)

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
async def logout(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
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
    client_ip = _get_client_ip(request)

    # 1. Get current user (validates token)
    user = await get_current_user(request, db)

    # 2. Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="登录失效")
    token = auth_header[7:]  # Remove "Bearer " prefix

    # 3. Revoke token
    try:
        revoked_token = await token_crud.revoke_token(db, token=token)
        if not revoked_token:
            logger.warning("logout_token_not_found", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=401, detail="登录失效")

        logger.info("user_logged_out", qiao_id=user.qiao_id, ip=client_ip)

        return {}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "logout_failed", error=str(e), qiao_id=user.qiao_id, ip=client_ip, exc_info=True
        )
        raise HTTPException(status_code=500, detail="退出登录失败，请稍后再试")


@router.post("/phone", response_model=VerifyPhoneResponse)
async def verify_phone(
    request: Request, body: VerifyPhoneRequest, db: AsyncSession = Depends(get_db)
) -> VerifyPhoneResponse:
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
    client_ip = _get_client_ip(request)

    try:
        # 1. Normalize phone number
        try:
            normalized_phone = normalize_phone(body.phone)

            # Check if China phone
            if not is_china_phone(normalized_phone):
                logger.warning("verify_phone_not_china_phone", phone=normalized_phone, ip=client_ip)
                raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")

        except ValueError as e:
            logger.error(
                "verify_phone_invalid_phone_format", phone=body.phone, error=str(e), ip=client_ip
            )
            raise HTTPException(status_code=400, detail="手机号格式无效")

        # 2. Verify SMS code
        stored_data = _verification_codes.get(normalized_phone)
        if not stored_data:
            logger.warning("verify_phone_sms_code_not_found", phone=normalized_phone, ip=client_ip)
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        stored_code, expires_at = stored_data
        if datetime.now(UTC) >= expires_at:
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

            logger.info(
                "verify_phone_wechat_code_verified", openid=wechat_openid[:8] + "...", ip=client_ip
            )

        # 4. Check if user exists
        user = await user_crud.get_by_phone(db, phone=normalized_phone)

        if user:
            # User exists - direct login
            logger.info(
                "verify_phone_user_exists",
                qiao_id=user.qiao_id,
                phone=normalized_phone,
                ip=client_ip,
            )

            # Bind WeChat openid if provided and not already bound
            if wechat_openid:
                existing_binding = await user_auth_crud.get_by_provider_uid(
                    db, auth_type=AuthType.WECHAT, provider_uid=wechat_openid
                )
                if existing_binding and existing_binding.user_id != user.id:
                    logger.warning(
                        "verify_phone_wechat_already_bound",
                        bound_user_id=existing_binding.user_id,
                        qiao_id=user.qiao_id,
                        ip=client_ip,
                    )
                    raise HTTPException(status_code=409, detail="该微信已绑定其它账号")
                if not existing_binding:
                    await user_auth_crud.create_binding(
                        db,
                        user_id=user.id,
                        user_qiao_id=user.qiao_id,
                        auth_type=AuthType.WECHAT,
                        provider_uid=wechat_openid,
                    )
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
                expires_in_seconds = await _get_jwt_expiration_seconds(db)
                jwt_token = generate_jwt_token(
                    user_id=user.id,
                    qiao_id=user.qiao_id,
                    device_type=DeviceType.MINI_PROGRAM,
                    expires_in_seconds=expires_in_seconds,
                )
                expires_at = calculate_token_expiry(expires_in_seconds)

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

            profile_result = await db.execute(
                select(Profile).where(
                    Profile.owner_id == user.id, Profile.owner_type == ProfileOwnerType.USER
                )
            )
            profile = profile_result.scalar_one_or_none()

            avatar_url = await get_avatar_url(db, profile)

            # Return login response
            return VerifyPhoneResponse(
                is_new_user=False,
                token=jwt_token,
                user={
                    "qiao_id": user.qiao_id,
                    "phone": user.phone,
                    "nickname": profile.nickname if profile else None,
                    "gender": profile.gender if profile else 0,
                    "avatar_url": avatar_url,
                    "bio": profile.bio if profile else None,
                },
            )

        # User doesn't exist - return temporary token for registration
        logger.info("verify_phone_new_user", phone=normalized_phone, ip=client_ip)

        # Generate temporary token
        verified_phone_token = _generate_verified_phone_token(normalized_phone, wechat_openid)

        # Clear verification code
        _verification_codes.pop(normalized_phone, None)

        # Return registration token
        return VerifyPhoneResponse(
            is_new_user=True,
            token=None,
            user=None,
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
) -> CompleteRegistrationResponse:
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
    client_ip = _get_client_ip(request)

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

        # Validate avatar file (optional)
        avatar_file_id_int = None
        if body.avatar_file_id:
            media_file = await media_file_crud.get_by_file_id(db, file_id=body.avatar_file_id)
            if not media_file:
                raise HTTPException(status_code=404, detail="头像文件不存在")
            if media_file.status != int(FileStatus.ACTIVE):
                raise HTTPException(status_code=400, detail="头像文件未激活")
            avatar_file_id_int = media_file.id

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
            user_id = generate_snowflake_id()
            qiao_id = generate_qiao_id()

            # Create user (account info only)
            user = User(
                id=user_id,
                qiao_id=qiao_id,
                phone=phone,
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
                avatar_file_id=avatar_file_id_int,
            )

            db.add(profile)
            await db.commit()
            await db.refresh(user)
            await db.refresh(profile)

            avatar_url = await get_avatar_url(db, profile)

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

        # 4. Create binding if provided
        try:
            if wechat_openid:
                existing_binding = await user_auth_crud.get_by_provider_uid(
                    db, auth_type=AuthType.WECHAT, provider_uid=wechat_openid
                )
                if existing_binding and existing_binding.user_id != user.id:
                    logger.warning(
                        "complete_registration_wechat_already_bound",
                        bound_user_id=existing_binding.user_id,
                        qiao_id=user.qiao_id,
                        ip=client_ip,
                    )
                    raise HTTPException(status_code=409, detail="该微信已绑定其它账号")
                if not existing_binding:
                    await user_auth_crud.create_binding(
                        db,
                        user_id=user.id,
                        user_qiao_id=user.qiao_id,
                        auth_type=AuthType.WECHAT,
                        provider_uid=wechat_openid,
                    )
                    logger.info(
                        "complete_registration_wechat_bound",
                        qiao_id=user.qiao_id,
                        openid=wechat_openid[:8] + "...",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("complete_registration_binding_failed", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="绑定失败，请稍后再试")

        # 5. Create token
        try:
            expires_in_seconds = await _get_jwt_expiration_seconds(db)
            jwt_token = generate_jwt_token(
                user_id=user.id,
                qiao_id=user.qiao_id,
                device_type=DeviceType.MINI_PROGRAM,
                expires_in_seconds=expires_in_seconds,
            )
            expires_at = calculate_token_expiry(expires_in_seconds)

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

        # 6. Return response
        return CompleteRegistrationResponse(
            token=jwt_token,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "nickname": profile.nickname,
                "gender": profile.gender,
                "avatar_url": avatar_url,
                "bio": profile.bio,
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("complete_registration_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试")


@router.post("/user/verify/send-code", response_model=VerifySendCodeResponse)
async def send_verification_code(
    body: VerifySendCodeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifySendCodeResponse:
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
            # On-demand CAPTCHA for each phone verification code send
            client_ip = _get_client_ip(request)
            try:
                provider = await create_captcha_provider_for_request("user", db, request)
                if not isinstance(provider, NoneCaptchaProvider):
                    if not body.captcha_token:
                        # Ask client to complete CAPTCHA first
                        raise HTTPException(
                            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                            detail={
                                "error": "CAPTCHA_REQUIRED",
                                "provider": "aliyun",
                                "message": "需要完成人机验证后再试",
                            },
                        )

                    is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
                    if not is_valid:
                        logger.warning("verify_send_code_captcha_failed", error=error)
                        raise HTTPException(status_code=400, detail="验证失败，请稍后再试")
                logger.info("verify_send_code_captcha_verified", user_id=current_user.id)
            except HTTPException:
                raise
            except Exception as e:
                logger.error("verify_send_code_captcha_error", error=str(e), exc_info=True)
                raise HTTPException(status_code=500, detail="验证服务错误，请稍后再试")

            target = body.target if body.target else current_user.phone
            if not target:
                raise HTTPException(status_code=400, detail="用户未绑定手机号")

            # Normalize phone
            normalized_phone = normalize_phone(target)

            # Check rate limit (reuse SMS group limits from system config)
            allowed, error_code, retry_after = await check_rate_limit(normalized_phone, "sms", db)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": error_code,
                        "message": "短信发送过于频繁，请稍后再试",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after) if retry_after else "60"},
                )

            # Generate verification code
            code = f"{secrets.randbelow(900000) + 100000}"

            # Store code
            expires_at = datetime.now(UTC) + timedelta(minutes=5)
            _verification_codes[normalized_phone] = (code, expires_at)
            _cleanup_expired_codes()

            # Send SMS via configured provider
            sms_provider = await create_sms_provider(db)
            result = await sms_provider.send_verification_code(normalized_phone, code)

            if not result.success:
                logger.error(
                    "verification_code_send_failed",
                    phone=normalized_phone,
                    user_id=current_user.id,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )
                raise HTTPException(status_code=500, detail="发送验证码失败，请稍后再试")

            logger.info(
                "verification_code_sent",
                phone=normalized_phone,
                user_id=current_user.id,
                provider_id=result.provider_id,
            )

            return VerifySendCodeResponse(cooldown=60)

        if body.verify_type == "email":
            target = body.target if body.target else current_user.email
            if not target:
                raise HTTPException(status_code=400, detail="用户未绑定邮箱")

            # TODO: Implement email verification code sending
            # For now, raise not implemented error
            raise HTTPException(status_code=501, detail="邮箱验证功能暂未实现")

        raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "send_verification_code_failed", error=str(e), user_id=current_user.id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="发送验证码失败，请稍后再试")


@router.post("/user/verify/confirm", response_model=OperationTokenResponse)
async def confirm_verification_code(
    body: VerifyConfirmRequest,
    current_user: User = Depends(get_current_user),
) -> OperationTokenResponse:
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

            if datetime.now(UTC) >= expires_at:
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

        if body.verify_type == "email":
            # TODO: Implement email verification
            raise HTTPException(status_code=501, detail="邮箱验证功能暂未实现")

        raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "confirm_verification_failed", error=str(e), user_id=current_user.id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="验证失败，请稍后再试")
