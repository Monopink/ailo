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
from services.security.auth_tracker import (
    check_lockout,
    record_auth_failure,
    reset_failures,
    should_require_captcha,
)
from services.security.captcha.factory import create_captcha_provider
from crud.system import system_configs
from crud.user import user as user_crud, user_token as token_crud
from models.user import User, UserToken
from enums import DeviceType
from utils.logging import get_logger
from utils.token import generate_jwt_token, calculate_token_expiry
from models.base import generate_qiao_id
from core.security import get_password_hash
from services.wechat.client import WeChatClient, WeChatAPIError
from services.wechat import code_manager
from utils.phone import normalize_phone, is_china_phone
from schemas.auth import (
    WeChatLoginRequest,
    WeChatLoginResponse,
    BindPhoneRequest,
    BindPhoneResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory verification code storage (for MVP)
# Format: phone -> (code, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verification_codes: Dict[str, Tuple[str, datetime]] = {}


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


# ============================================================================
# User Authentication Schemas
# ============================================================================


class SendSMSRequest(BaseModel):
    """Request model for sending SMS verification code"""

    phone: str = Field(..., description="Phone number (11 digits)")


class SendSMSResponse(BaseModel):
    """Response model for sending SMS"""

    message: str


class RegisterRequest(BaseModel):
    """Request model for user registration"""

    phone: str = Field(..., description="Phone number (11 digits)")
    code: str = Field(..., description="Verification code (6 digits)")
    password: str = Field(..., min_length=6, max_length=32, description="Password (6-32 characters)")


class RegisterResponse(BaseModel):
    """Response model for user registration"""

    qiao_id: str
    phone: str
    token: str  # Session token
    message: str


class LoginSMSRequest(BaseModel):
    """Request model for SMS login"""

    phone: str = Field(..., description="Phone number (11 digits)")
    code: str = Field(..., description="Verification code (6 digits)")


class LoginResponse(BaseModel):
    """Response model for login"""

    qiao_id: str
    phone: str
    token: str  # Session token
    message: str


# ============================================================================
# Message Client Signature Schemas
# ============================================================================


class MessageClientSignatureRequest(BaseModel):
    """Request model for message client signature"""

    client_id: str


class MessageClientSignatureResponse(BaseModel):
    """Response model for message client signature"""

    signature: str
    timestamp: int
    nonce: str
    client_id: str


# ============================================================================
# User Authentication Endpoints
# ============================================================================


@router.post("/send-sms", response_model=SendSMSResponse)
async def send_sms_code(request: Request, body: SendSMSRequest, db: AsyncSession = Depends(get_db)):
    """
    Send SMS verification code.

    Security:
    - Rate limit: 1 request per 60 seconds per phone number
    - Phone number validation
    - Generates 6-digit random code

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


@router.post("/register", response_model=RegisterResponse)
async def register_user(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    User registration with SMS verification.

    Security:
    - Rate limit: 10 requests per 3600 seconds per IP
    - Authentication failure tracking
    - Lockout mechanism
    - Optional CAPTCHA
    - SMS verification code validation
    - Invite code validation (TODO: Not implemented yet)

    Args:
        request: FastAPI request
        body: Registration data
        db: Database session

    Returns:
        RegisterResponse with user info and token

    Raises:
        HTTPException: 400/429/500 for various errors
    """
    client_ip = request.client.host

    # 1. Validate phone format
    try:
        normalized_phone = normalize_phone(body.phone)
        if not is_china_phone(normalized_phone):
            raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")
    except ValueError:
        raise HTTPException(status_code=400, detail="手机号格式无效")

    # 2. Check lockout
    is_locked, remaining_seconds = await check_lockout(client_ip, "user_auth", db)
    if is_locked:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "ACCOUNT_LOCKED",
                "message": "认证失败次数过多，请稍后再试",
                "retry_after": remaining_seconds,
            },
            headers={"Retry-After": str(remaining_seconds)},
        )

    # 3. Check CAPTCHA if needed
    captcha_required = await should_require_captcha(client_ip, "user_auth", db)
    if captcha_required:
        # TODO: Implement CAPTCHA verification
        # Current status: CAPTCHA provider abstraction exists in services/security/captcha/
        # Implementation steps:
        # 1. Add captcha_token field to RegisterRequest schema
        # 2. Import create_captcha_provider from services.security.captcha.factory
        # 3. Call provider = await create_captcha_provider("user", db)
        # 4. Call is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
        # 5. Raise HTTPException if verification fails
        # For MVP: Skip CAPTCHA verification
        logger.warning("captcha_required_but_skipped", ip=client_ip, endpoint="register")

    # 4. Verify SMS code
    stored_data = _verification_codes.get(normalized_phone)
    if not stored_data:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_not_found", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    stored_code, expires_at = stored_data
    if datetime.utcnow() >= expires_at:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_expired", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码已过期")

    if stored_code != body.code:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_mismatch", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码错误")

    # 5. Check if phone already registered
    existing_user = await user_crud.get_by_phone(db, phone=normalized_phone)
    if existing_user:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("registration_phone_already_exists", phone=body.phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="该手机号已注册")

    # 6. Create user
    try:
        from utils.snowflake import generate_snowflake_id

        # Generate IDs
        user_id = generate_snowflake_id()
        qiao_id = generate_qiao_id()
        password_hash = get_password_hash(body.password)

        # Create user object directly
        new_user = User(
            id=user_id,
            qiao_id=qiao_id,
            phone=normalized_phone,
            password_hash=password_hash,
            username=f"用户{qiao_id[-6:]}",
            user_type=1,  # Normal user
            status=1,  # Active
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info("user_registered", qiao_id=qiao_id, phone=normalized_phone, ip=client_ip)

    except Exception as e:
        logger.error("user_creation_failed", error=str(e), phone=normalized_phone, exc_info=True)
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试")

    # 7. Create token
    try:
        from utils.snowflake import generate_snowflake_id

        jwt_token = generate_jwt_token(
            user_id=new_user.id, qiao_id=new_user.qiao_id, device_type=DeviceType.WEB
        )
        expires_at = calculate_token_expiry()

        # Create token object directly
        user_token = UserToken(
            id=generate_snowflake_id(),
            user_id=new_user.id,
            user_qiao_id=new_user.qiao_id,
            token=jwt_token,
            device_type=DeviceType.WEB,  # Default to web for MVP
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

        logger.info("token_created", qiao_id=qiao_id, token=jwt_token[:16] + "...")

    except Exception as e:
        logger.error("token_creation_failed", error=str(e), qiao_id=qiao_id, exc_info=True)
        raise HTTPException(status_code=500, detail="注册失败，请稍后再试")

    # 8. Clear verification code
    _verification_codes.pop(normalized_phone, None)

    # 9. Reset authentication failures
    await reset_failures(client_ip, "user_auth")

    # 10. Return response
    return RegisterResponse(
        qiao_id=new_user.qiao_id, phone=new_user.phone, token=jwt_token, message="注册成功"
    )


@router.post("/login/sms", response_model=LoginResponse)
async def login_sms(request: Request, body: LoginSMSRequest, db: AsyncSession = Depends(get_db)):
    """
    SMS-based login.

    Security:
    - Rate limit: 10 requests per 3600 seconds per IP
    - Authentication failure tracking
    - Lockout mechanism
    - Optional CAPTCHA
    - SMS verification code validation
    - Device limit enforcement (1 session per device type)

    Args:
        request: FastAPI request
        body: Login data
        db: Database session

    Returns:
        LoginResponse with user info and token

    Raises:
        HTTPException: 400/429/500 for various errors
    """
    client_ip = request.client.host

    # 1. Validate phone format
    try:
        normalized_phone = normalize_phone(body.phone)
        if not is_china_phone(normalized_phone):
            raise HTTPException(status_code=400, detail="仅支持中国大陆手机号")
    except ValueError:
        raise HTTPException(status_code=400, detail="手机号格式无效")

    # 2. Check lockout
    is_locked, remaining_seconds = await check_lockout(client_ip, "user_auth", db)
    if is_locked:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "ACCOUNT_LOCKED",
                "message": "认证失败次数过多，请稍后再试",
                "retry_after": remaining_seconds,
            },
            headers={"Retry-After": str(remaining_seconds)},
        )

    # 3. Check CAPTCHA if needed
    captcha_required = await should_require_captcha(client_ip, "user_auth", db)
    if captcha_required:
        # TODO: Implement CAPTCHA verification
        # Current status: CAPTCHA provider abstraction exists in services/security/captcha/
        # Implementation steps:
        # 1. Add captcha_token field to LoginRequest schema
        # 2. Import create_captcha_provider from services.security.captcha.factory
        # 3. Call provider = await create_captcha_provider("user", db)
        # 4. Call is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
        # 5. Raise HTTPException if verification fails
        # For MVP: Skip CAPTCHA verification
        logger.warning("captcha_required_but_skipped", ip=client_ip, endpoint="login")

    # 4. Verify SMS code
    stored_data = _verification_codes.get(normalized_phone)
    if not stored_data:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_not_found", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    stored_code, expires_at = stored_data
    if datetime.utcnow() >= expires_at:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_expired", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码已过期")

    if stored_code != body.code:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("sms_code_mismatch", phone=normalized_phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="验证码错误")

    # 5. Find user
    user = await user_crud.get_by_phone(db, phone=normalized_phone)
    if not user:
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("login_user_not_found", phone=body.phone, ip=client_ip)
        raise HTTPException(status_code=400, detail="用户不存在")

    # 6. Check user status
    if not await user_crud.is_active(user):
        await record_auth_failure(client_ip, "user_auth", db)
        logger.warning("login_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
        raise HTTPException(status_code=400, detail="账号已被禁用")

    # 7. Handle device limit (revoke old tokens for same device type)
    try:
        device_type = DeviceType.WEB  # Default to web for MVP
        revoked_count = await token_crud.revoke_user_tokens_by_device(
            db, user_id=user.id, device_type=device_type
        )
        if revoked_count > 0:
            logger.info(
                "old_tokens_revoked",
                qiao_id=user.qiao_id,
                device_type=device_type,
                count=revoked_count,
            )
    except Exception as e:
        logger.error("token_revocation_failed", error=str(e), qiao_id=user.qiao_id, exc_info=True)
        # Continue even if revocation fails

    # 8. Create new token
    try:
        from utils.snowflake import generate_snowflake_id

        jwt_token = generate_jwt_token(user_id=user.id, qiao_id=user.qiao_id, device_type=DeviceType.WEB)
        expires_at = calculate_token_expiry()

        # Create token object directly
        user_token = UserToken(
            id=generate_snowflake_id(),
            user_id=user.id,
            user_qiao_id=user.qiao_id,
            token=jwt_token,
            device_type=DeviceType.WEB,  # Default to web for MVP
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

        logger.info("token_created", qiao_id=user.qiao_id, token=jwt_token[:16] + "...")

    except Exception as e:
        logger.error("token_creation_failed", error=str(e), qiao_id=user.qiao_id, exc_info=True)
        raise HTTPException(status_code=500, detail="登录失败，请稍后再试")

    # 9. Clear verification code
    _verification_codes.pop(body.phone, None)

    # 10. Reset authentication failures
    await reset_failures(client_ip, "user_auth")

    # 11. Return response
    return LoginResponse(qiao_id=user.qiao_id, phone=user.phone, token=jwt_token, message="登录成功")


# ============================================================================
# Message Client Signature Endpoints
# ============================================================================


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


# ============================================================================
# WeChat Authentication Endpoints
# ============================================================================


@router.post("/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(request: Request, body: WeChatLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    WeChat Mini Program login

    Flow:
    1. Exchange login_code for openid
    2. Exchange phone_code for phone number
    3. Check phone number:
       - If China phone (+86): Register/login user
       - If international phone: Return needs_phone_binding=True
       - If invalid format: Return needs_phone_binding=True
    4. Create session and return user info

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

        # 9. Return response
        return WeChatLoginResponse(
            success=True,
            needs_phone_binding=False,
            user={
                "qiao_id": user.qiao_id,
                "phone": user.phone,
                "username": user.username,
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

    Flow:
    1. Verify wechat_code to get openid
    2. Verify SMS code
    3. Normalize phone number
    4. Find or create user
    5. Create session and return user info

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
