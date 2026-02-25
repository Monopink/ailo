"""Authentication API endpoints.

This module provides authentication-related endpoints including:
- SMS verification code sending
- User registration
- User login (SMS-based)
- Message client signature generation for LeanCloud IM authentication
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.crud.profile import profile as profile_crud
from app.crud.system import system_configs
from app.crud.user import login_record as login_record_crud
from app.crud.user import user as user_crud
from app.crud.user import user_auth as user_auth_crud
from app.crud.user import user_token as token_crud
from app.enums import AuthType, DeviceType, LoginResult, LoginType, ProfileOwnerType
from app.exceptions.error_codes import build_protective_denial_detail
from app.models.base import generate_qiao_id
from app.models.profile import Profile
from app.models.user import User, UserAuth, UserToken
from app.schemas.auth import (
    PasswordLoginRequest,
    PasswordLoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    VerifyPhoneRequest,
    VerifyPhoneResponse,
    WeChatBindPhoneRequest,
    WeChatBindPhoneResponse,
    WeChatLoginRequest,
    WeChatLoginResponse,
    WeChatRefreshPhoneRequest,
    WeChatRefreshPhoneResponse,
)
from app.schemas.profile import ProfileCreate
from app.schemas.user import LoginRecordCreate
from app.schemas.verify import (
    OperationTokenResponse,
    VerifyConfirmRequest,
    VerifySendCodeRequest,
    VerifySendCodeResponse,
)
from app.services.profile.avatar import get_avatar_url
from app.services.security.auth_tracker import check_lockout, record_auth_failure, reset_failures
from app.services.security.captcha.factory import (
    create_captcha_provider_for_request,
)
from app.services.security.captcha.none import NoneCaptchaProvider
from app.services.security.rate_limiter import check_password_login_rate_limit, check_rate_limit
from app.services.security.sms.factory import create_sms_provider
from app.services.wechat.client import WeChatAPIError, WeChatClient
from app.type_defs import JSONDict, JSONValue
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger
from app.utils.phone import is_china_phone, mask_phone, normalize_phone
from app.utils.snowflake import generate_snowflake_id
from app.utils.token import calculate_token_expiry, generate_jwt_token

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

settings = get_settings()

WECHAT_TEST_PHONE_NUMBERS = frozenset({"12066600001", "12066600002", "12066600003", "12066600004"})
WECHAT_PHONE_MOCK_ENABLED_KEY = "wechat_phone_mock_enabled"
WECHAT_PHONE_MOCK_NUMBER_KEY = "wechat_phone_mock_number"

# In-memory verification code storage (for MVP)
# Format: phone -> (code, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_verification_codes: dict[str, tuple[str, datetime]] = {}

# In-memory operation token storage (for MVP)
# Format: token -> (user_id, expires_at)
# TODO: Replace with Redis in production for distributed deployment
_operation_tokens: dict[str, tuple[int, datetime]] = {}

# Constants
SMS_CODE_TTL_SECONDS = 5 * 60  # 5 minutes
SMS_COOLDOWN_SECONDS = 60

_refresh_token_requests: dict[str, list[datetime]] = {}
REFRESH_RATE_LIMIT = 5
REFRESH_RATE_WINDOW = timedelta(minutes=1)


def _protective_denial_detail(
    *,
    reason: str,
    camouflage_message: str = "操作异常",
    camouflage_status_code: int = status.HTTP_400_BAD_REQUEST,
    **metadata: object,
) -> dict[str, object]:
    """Create detail payload for protective-denial responses."""
    detail_metadata = metadata or None
    return build_protective_denial_detail(
        reason=reason,
        camouflage_status_code=camouflage_status_code,
        camouflage_message=camouflage_message,
        metadata=detail_metadata,
    )


@dataclass
class TokenPair:
    """Access and refresh tokens issued together."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_token_id: int


@dataclass
class AccessTokenInfo:
    """Metadata describing an access token."""

    access_token: str
    expires_in: int


def _get_client_ip(request: Request) -> str:
    """Safely get client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address extracted from trusted proxy header

    """
    try:
        return get_client_ip(request)
    except ClientIPResolutionError as exc:
        logger.warning("auth_client_ip_invalid", reason=exc.reason, detail=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求来源无效",
        ) from exc


async def _record_login_attempt(
    db: AsyncSession,
    *,
    user: User | None,
    login_type: LoginType,
    platform: DeviceType,
    device_id: UUID | None,
    result: LoginResult,
    fail_reason: str | None,
    client_ip: str,
    user_agent: str | None,
    user_token_id: int | None = None,
) -> None:
    """Persist a login attempt audit record without breaking auth flow."""
    try:
        await login_record_crud.create(
            db,
            obj_in=LoginRecordCreate(
                user_id=user.id if user else None,
                user_qiao_id=user.qiao_id if user else None,
                login_type=login_type,
                platform=platform,
                device_id=device_id,
                ip_address=client_ip,
                user_agent=user_agent,
                result=result,
                fail_reason=fail_reason,
                user_token_id=user_token_id,
            ),
        )
    except Exception:
        logger.error(
            "login_record_write_failed",
            login_type=login_type.value,
            platform=platform.value,
            has_user=user is not None,
            result=result.value,
        )


async def _get_jwt_expiration_seconds(db: AsyncSession) -> int:
    """Return JWT expiration duration in seconds from configuration."""
    expires_in_days = await system_configs.get_config_value(
        db, config_key="jwt_token_expires_in_days"
    )
    expires_in = _coerce_int(expires_in_days)
    if expires_in is None:
        logger.error("jwt_expiration_config_missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )

    return expires_in * 86400


async def _get_refresh_token_expiration_days(db: AsyncSession) -> int:
    """Return refresh token expiration duration in days."""
    refresh_in_days = await system_configs.get_config_value(
        db, config_key="refresh_token_expires_in_days", default_value=90
    )
    days = _coerce_int(refresh_in_days)
    if days is None:
        logger.warning("refresh_token_expiration_invalid", value=refresh_in_days)
        return 90
    return max(days, 1)


def _enforce_refresh_rate_limit(refresh_hash: str) -> None:
    """Prevent the same refresh token from being used too frequently."""
    now = datetime.now(UTC)
    window_start = now - REFRESH_RATE_WINDOW
    history = [ts for ts in _refresh_token_requests.get(refresh_hash, []) if ts > window_start]
    if len(history) >= REFRESH_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="REFRESH_RATE_LIMIT",
                camouflage_message="登录已失效，请重新登录",
            ),
        )
    history.append(now)
    _refresh_token_requests[refresh_hash] = history


def _cleanup_expired_codes() -> None:
    """Clean up expired verification codes from memory.

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


def _cleanup_expired_operation_tokens() -> None:
    """Clean up expired operation tokens from memory.

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


async def _apply_wechat_phone_mock(
    db: AsyncSession,
    phone_info: JSONDict,
) -> JSONDict:
    """Replace phone data with configured mock number when using WeChat virtual accounts.

    Args:
        db: Database session
        phone_info: WeChat phone info payload

    Returns:
        Potentially modified phone info dictionary

    """
    if not isinstance(phone_info, dict) or settings.is_production:
        return phone_info

    enabled_value = await system_configs.get_config_value(
        db,
        config_key=WECHAT_PHONE_MOCK_ENABLED_KEY,
        default_value=False,
    )
    enabled = (
        enabled_value.lower() in {"true", "1", "yes", "on"}
        if isinstance(enabled_value, str)
        else bool(enabled_value)
    )
    if not enabled:
        return phone_info

    pure_phone = phone_info.get("purePhoneNumber")
    if not pure_phone or pure_phone not in WECHAT_TEST_PHONE_NUMBERS:
        return phone_info

    mock_phone = await system_configs.get_config_value(
        db,
        config_key=WECHAT_PHONE_MOCK_NUMBER_KEY,
        default_value=None,
    )
    if not mock_phone:
        logger.warning(
            "wechat_phone_mock_missing_number",
            pure_phone=pure_phone,
        )
        return phone_info

    mocked_info = dict(phone_info)
    mock_phone_str = "".join(ch for ch in str(mock_phone).strip() if ch.isdigit())
    if not mock_phone_str:
        logger.warning(
            "wechat_phone_mock_invalid_number",
            original_value=mock_phone,
            pure_phone=pure_phone,
        )
        return phone_info

    mocked_info["purePhoneNumber"] = mock_phone_str
    mocked_info["phoneNumber"] = mock_phone_str
    mocked_info["countryCode"] = mocked_info.get("countryCode") or "86"

    logger.info(
        "wechat_phone_mock_applied",
        original_phone=pure_phone,
        mock_phone=mock_phone_str,
    )

    return mocked_info


def _consume_sms_code(phone: str, sms_code: str) -> None:
    """Validate and consume a previously issued SMS verification code.

    Args:
        phone: Normalized E.164 phone number
        sms_code: Code provided by client

    Raises:
        HTTPException: If code is missing, expired, or mismatched

    """
    stored_data = _verification_codes.get(phone)
    if not stored_data:
        raise HTTPException(status_code=400, detail="验证码有误，请重新输入")

    stored_code, expires_at = stored_data
    if datetime.now(UTC) >= expires_at:
        del _verification_codes[phone]
        raise HTTPException(status_code=400, detail="验证码已失效，请重新获取")

    if stored_code != sms_code:
        raise HTTPException(status_code=400, detail="验证码有误，请重新输入")

    del _verification_codes[phone]


def _generate_operation_token(user_id: int) -> str:
    """Generate an operation token for sensitive operations.

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
    """Verify operation token and return user ID.

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


async def _rotate_access_token(
    db: AsyncSession,
    *,
    user_token: UserToken,
) -> AccessTokenInfo:
    """Rotate access token for existing session."""
    expires_in_seconds = await _get_jwt_expiration_seconds(db)
    access_token = generate_jwt_token(
        user_id=user_token.user_id,
        qiao_id=user_token.user_qiao_id,
        device_type=DeviceType(user_token.device_type),
        expires_in_seconds=expires_in_seconds,
        session_id=user_token.id,
    )
    access_expires_at = calculate_token_expiry(expires_in_seconds)

    user_token.access_token = access_token
    user_token.access_expires_at = access_expires_at
    user_token.last_activity_at = datetime.now(UTC)
    user_token.access_revoked_at = None
    db.add(user_token)
    await db.commit()
    await db.refresh(user_token)
    return AccessTokenInfo(access_token=access_token, expires_in=expires_in_seconds)


async def _issue_jwt_token_for_user(
    db: AsyncSession,
    *,
    user: User,
    client_ip: str,
    user_agent: str | None,
    log_event: str,
    device_type: DeviceType,
    device_id: UUID,
) -> TokenPair:
    """Create and persist a JWT token for the given user."""
    expires_in_seconds = await _get_jwt_expiration_seconds(db)
    refresh_days = await _get_refresh_token_expiration_days(db)
    user_token_id = generate_snowflake_id()

    jwt_token = generate_jwt_token(
        user_id=user.id,
        qiao_id=user.qiao_id,
        device_type=device_type,
        expires_in_seconds=expires_in_seconds,
        session_id=user_token_id,
    )
    expires_at = calculate_token_expiry(expires_in_seconds)
    refresh_token = secrets.token_urlsafe(64)
    refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    refresh_expires_at = datetime.now(UTC) + timedelta(days=refresh_days)

    user_token = UserToken(
        id=user_token_id,
        user_id=user.id,
        user_qiao_id=user.qiao_id,
        access_token=jwt_token,
        device_type=device_type,
        device_id=device_id,
        platform_info=None,
        ip_address=client_ip,
        user_agent=user_agent,
        access_expires_at=expires_at,
        status=1,
        last_activity_at=datetime.now(UTC),
        access_revoked_at=None,
        refresh_token_hash=refresh_token_hash,
        refresh_expires_at=refresh_expires_at,
        refresh_revoked_at=None,
        token_metadata={},
    )

    db.add(user_token)
    await db.commit()
    await db.refresh(user_token)

    logger.info(log_event, qiao_id=user.qiao_id)

    return TokenPair(
        access_token=jwt_token,
        refresh_token=refresh_token,
        expires_in=expires_in_seconds,
        user_token_id=user_token_id,
    )


@router.post("/login", response_model=PasswordLoginResponse)
async def password_login(
    request: Request,
    body: PasswordLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> PasswordLoginResponse:
    """Password login (username/phone/email + password)."""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    device_type = body.device_type

    identifier = body.identifier.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="登录失败")

    username: str | None = None
    phone: str | None = None
    email: str | None = None

    # Heuristics:
    # - Contains '@' => email
    # - Otherwise if looks like CN phone => normalize to E.164
    # - Else => username
    if "@" in identifier:
        email = identifier.lower()
    elif is_china_phone(identifier):
        phone = normalize_phone(identifier)
    else:
        username = identifier

    identifier_key = str(email or phone or username or identifier).lower()
    auth_identifier = f"{client_ip}:{identifier_key}"

    locked, remaining = await check_lockout(auth_identifier, "user_auth", db)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="AUTH_LOCKED_OUT",
                camouflage_message="登录失败，请稍后再试",
                retry_after=remaining,
            ),
        )

    allowed, error_code, retry_after = await check_password_login_rate_limit(auth_identifier, db)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="AUTH_PASSWORD_RATE_LIMIT",
                camouflage_message="登录失败，请稍后再试",
                limiter_error=error_code,
                retry_after=retry_after,
            ),
        )

    user = await user_crud.authenticate(
        db,
        username=username,
        phone=phone,
        email=email,
        password=body.password,
    )
    if not user:
        await _record_login_attempt(
            db,
            user=user,
            login_type=LoginType.PASSWORD,
            platform=device_type,
            device_id=body.device_id,
            result=LoginResult.FAIL,
            fail_reason="INVALID_CREDENTIALS",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await record_auth_failure(auth_identifier, "user_auth", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号或密码错误",
        )

    if not await user_crud.is_active(user):
        await _record_login_attempt(
            db,
            user=user,
            login_type=LoginType.PASSWORD,
            platform=device_type,
            device_id=body.device_id,
            result=LoginResult.FAIL,
            fail_reason="USER_STATUS_NOT_ACTIVE",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await record_auth_failure(auth_identifier, "user_auth", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号已被禁用",
        )

    await reset_failures(auth_identifier, "user_auth")

    token_pair = await _issue_jwt_token_for_user(
        db,
        user=user,
        client_ip=client_ip,
        user_agent=user_agent,
        log_event="password_login_token_created",
        device_type=device_type,
        device_id=body.device_id,
    )
    await _record_login_attempt(
        db,
        user=user,
        login_type=LoginType.PASSWORD,
        platform=device_type,
        device_id=body.device_id,
        result=LoginResult.SUCCESS,
        fail_reason=None,
        user_token_id=token_pair.user_token_id,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    profile = await _ensure_profile_stub(db, user=user)
    avatar_url = await get_avatar_url(profile)

    return PasswordLoginResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
        needs_profile_setup=bool(user.needs_profile_setup),
        user=_build_user_payload(user, profile, avatar_url),
    )


async def _ensure_profile_stub(
    db: AsyncSession, *, user: User, nickname: str | None = None
) -> Profile:
    """Ensure the specified user has a profile stub (NULL avatar_key default)."""
    profile_result = await db.execute(
        select(Profile).where(
            Profile.owner_id == user.id,
            Profile.owner_type == ProfileOwnerType.USER,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile:
        return profile

    profile = await profile_crud.create_with_owner(
        db,
        obj_in=ProfileCreate(
            nickname=nickname or f"用户{user.qiao_id[-6:]}",
            avatar_key=None,
            avatar_media_id=None,
        ),
        owner_id=user.id,
        owner_qiao_id=user.qiao_id,
        owner_type=ProfileOwnerType.USER,
    )
    logger.info("profile_stub_created", qiao_id=user.qiao_id)
    return profile


def _build_user_payload(
    user: User, profile: Profile | None, avatar_url: str
) -> dict[str, JSONValue]:
    """Construct user payload for authentication responses."""
    return {
        "qiao_id": user.qiao_id,
        "phone": user.phone,
        "nickname": profile.nickname if profile else None,
        "gender": profile.gender if profile else None,
        "avatar_url": avatar_url,
        "bio": profile.bio if profile else None,
    }


class SendSMSRequest(BaseModel):
    """Request model for sending SMS verification code."""

    phone: str = Field(..., description="Phone number (11 digits)")
    # Optional for on-demand verification. When CAPTCHA is enabled and
    # token is missing, API returns a user-actionable 400 error.
    # to perform human verification and retry with this token.
    captcha_token: str | None = Field(None, description="CAPTCHA verification token (on-demand)")


class SendSMSResponse(BaseModel):
    """Response model for sending SMS."""

    expires_in: int = Field(..., description="Verification code TTL in seconds")
    cooldown_seconds: int = Field(..., description="Cooldown before next send in seconds")


@router.post("/send-sms", response_model=SendSMSResponse)
async def send_sms_code(
    request: Request, body: SendSMSRequest, db: AsyncSession = Depends(get_db)
) -> SendSMSResponse:
    """Send SMS verification code.

    Args:
        request: FastAPI request
        body: Contains phone number
        db: Database session

    Returns:
        SendSMSResponse with success message

    Raises:
        HTTPException: 400 for invalid phone, 429 for rate limit

    """
    # 0. On-demand CAPTCHA: if enabled and missing token -> friendly 400
    try:
        client_ip = _get_client_ip(request)
        provider, captcha_meta = await create_captcha_provider_for_request("user", db, request)

        # If CAPTCHA is enabled, require token; otherwise skip
        if not isinstance(provider, NoneCaptchaProvider):
            if not body.captcha_token:
                # Signal client to perform CAPTCHA first
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_protective_denial_detail(
                        reason="SMS_CAPTCHA_REQUIRED",
                        camouflage_message="需要完成人机验证后再试",
                        captcha_metadata=captcha_meta.to_response(),
                    ),
                )

            is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
            if not is_valid:
                logger.warning("sms_captcha_failed", ip=client_ip, error=error)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_protective_denial_detail(
                        reason="SMS_CAPTCHA_INVALID",
                        camouflage_message="需要完成人机验证后再试",
                        captcha_error=error,
                    ),
                )
            logger.info("sms_captcha_verified", ip=client_ip)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("sms_captcha_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")

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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="SMS_RATE_LIMIT",
                camouflage_message="请30秒后再试",
                limiter_error=error_code,
                retry_after=retry_after,
            ),
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
        raise HTTPException(status_code=500, detail="系统错误")

    logger.info("sms_sent", phone=normalized_phone, provider_id=result.provider_id)

    return SendSMSResponse(expires_in=SMS_CODE_TTL_SECONDS, cooldown_seconds=SMS_COOLDOWN_SECONDS)


@router.post("/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(
    request: Request, body: WeChatLoginRequest, db: AsyncSession = Depends(get_db)
) -> WeChatLoginResponse:
    """WeChat Mini Program login stage 1: openid check only."""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    wechat_client = WeChatClient()

    try:
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]
        unionid = session_data.get("unionid")

        logger.info(
            "wechat_login_code2session_success",
            openid=openid[:8] + "...",
            unionid=(unionid[:8] + "..." if unionid else None),
            ip=client_ip,
        )

        existing_binding = await user_auth_crud.get_by_provider_uid(
            db, auth_type=AuthType.WECHAT, provider_uid=openid
        )

        if not existing_binding:
            logger.info("wechat_need_phone", openid=openid[:8] + "...", ip=client_ip)
            return WeChatLoginResponse(
                status="need_phone",
                access_token=None,
                refresh_token=None,
                expires_in=None,
                needs_profile_setup=None,
                user=None,
                message=None,
            )

        user = await user_crud.get(db, existing_binding.user_id)
        if not user:
            logger.error(
                "wechat_binding_dirty_data",
                openid=openid[:8] + "...",
                user_ids=[existing_binding.user_id],
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="登录遇到问题，请联系客服")

        if not await user_crud.is_active(user):
            await _record_login_attempt(
                db,
                user=user,
                login_type=LoginType.WECHAT,
                platform=DeviceType.MINI_PROGRAM,
                device_id=body.device_id,
                result=LoginResult.FAIL,
                fail_reason="ACCOUNT_INACTIVE",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            logger.warning("wechat_login_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        token_pair = await _issue_jwt_token_for_user(
            db,
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
            log_event="wechat_token_created",
            device_type=DeviceType.MINI_PROGRAM,
            device_id=body.device_id,
        )
        await _record_login_attempt(
            db,
            user=user,
            login_type=LoginType.WECHAT,
            platform=DeviceType.MINI_PROGRAM,
            device_id=body.device_id,
            result=LoginResult.SUCCESS,
            fail_reason=None,
            user_token_id=token_pair.user_token_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        profile = await _ensure_profile_stub(db, user=user)
        avatar_url = await get_avatar_url(profile)

        logger.info(
            "wechat_bound_user_login",
            user_id=user.id,
            qiao_id=user.qiao_id,
            openid=openid[:8] + "...",
            ip=client_ip,
        )

        return WeChatLoginResponse(
            status="bound",
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            needs_profile_setup=bool(user.needs_profile_setup),
            user=_build_user_payload(user, profile, avatar_url),
            message="登录成功",
        )

    except WeChatAPIError as e:
        logger.error(
            "wechat_api_error",
            errcode=e.errcode,
            errmsg=e.errmsg,
            ip=client_ip,
        )
        raise HTTPException(status_code=500, detail="系统错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("wechat_login_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/wechat/bind-phone", response_model=WeChatBindPhoneResponse)
async def bind_wechat_phone(
    request: Request, body: WeChatBindPhoneRequest, db: AsyncSession = Depends(get_db)
) -> WeChatBindPhoneResponse:
    """WeChat Mini Program login stage 2: bind phone and issue tokens."""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    wechat_client = WeChatClient()

    try:
        access_token = await wechat_client.get_access_token()
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]
        unionid = session_data.get("unionid")

        logger.info(
            "wechat_bind_code2session_success",
            openid=openid[:8] + "...",
            unionid=(unionid[:8] + "..." if unionid else None),
            ip=client_ip,
        )

        phone_data = await wechat_client.get_phone_number(body.phone_code, access_token)
        phone_info = await _apply_wechat_phone_mock(
            db,
            phone_data.get("phone_info", {}),
        )

        country_code = phone_info.get("countryCode")
        pure_phone = phone_info.get("purePhoneNumber")

        try:
            phone_e164 = f"+{country_code}{pure_phone}"
        except Exception:
            logger.warning(
                "wechat_phone_check_failed",
                openid=openid[:8] + "...",
                country_code=country_code,
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="暂不支持国际手机号")

        if not is_china_phone(phone_e164):
            logger.warning(
                "wechat_international_phone",
                openid=openid[:8] + "...",
                country_code=country_code,
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="暂不支持国际手机号")

        try:
            normalized_phone = normalize_phone(phone_e164)

            logger.info(
                "wechat_phone_normalized",
                openid=openid[:8] + "...",
                phone=normalized_phone,
                ip=client_ip,
            )

        except ValueError as e:
            logger.warning(
                "wechat_invalid_phone_format",
                openid=openid[:8] + "...",
                phone=pure_phone,
                error=str(e),
                ip=client_ip,
            )

            raise HTTPException(status_code=400, detail="手机号格式无效")

        logger.info(
            "wechat_bind_phone_start",
            openid=openid[:8] + "...",
            phone=normalized_phone,
            ip=client_ip,
        )

        user = await user_crud.get_by_phone(db, phone=normalized_phone)
        created_new_user = False
        replaced_old_wechat = False
        binding_reused = False
        binding_created = False
        needs_commit = False
        old_openid_for_log: str | None = None

        existing_binding_for_openid = await user_auth_crud.get_by_provider_uid(
            db, auth_type=AuthType.WECHAT, provider_uid=openid
        )

        if not user:
            try:
                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    username=None,
                    user_type=1,
                    status=1,
                    needs_profile_setup=True,
                )

                db.add(user)
                await db.commit()
                await db.refresh(user)
                created_new_user = True

                logger.info(
                    "wechat_new_user_created",
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
                raise HTTPException(status_code=500, detail="系统错误")

        # Resolve binding for existing user (or newly created one)
        user_binding_result = await db.execute(
            select(UserAuth).where(
                and_(
                    UserAuth.user_id == user.id,
                    UserAuth.auth_type == int(AuthType.WECHAT),
                    UserAuth.status == 1,
                )
            )
        )
        user_binding = user_binding_result.scalar_one_or_none()
        now = datetime.now(UTC)

        binding_obj: UserAuth | None = None

        if user_binding and user_binding.provider_uid == openid:
            binding_obj = user_binding
        else:
            if user_binding and user_binding.provider_uid != openid:
                old_openid_for_log = user_binding.provider_uid
                user_binding.status = 2
                user_binding.revoked_at = now
                db.add(user_binding)
                replaced_old_wechat = True
                needs_commit = True

            if existing_binding_for_openid and existing_binding_for_openid.user_id != user.id:
                existing_binding_for_openid.user_id = user.id
                existing_binding_for_openid.user_qiao_id = user.qiao_id
                existing_binding_for_openid.unionid = unionid
                existing_binding_for_openid.status = 1
                existing_binding_for_openid.revoked_at = None
                db.add(existing_binding_for_openid)
                binding_obj = existing_binding_for_openid
                replaced_old_wechat = True
                needs_commit = True
            elif existing_binding_for_openid and existing_binding_for_openid.user_id == user.id:
                binding_obj = existing_binding_for_openid
            else:
                binding_obj = await user_auth_crud.create_binding(
                    db,
                    user_id=user.id,
                    user_qiao_id=user.qiao_id,
                    auth_type=AuthType.WECHAT,
                    provider_uid=openid,
                    unionid=unionid,
                )
                binding_created = True

        if not created_new_user:
            binding_reused = True

        if replaced_old_wechat:
            logger.info(
                "wechat_binding_replaced",
                user_id=user.id,
                old_openid=old_openid_for_log,
                new_openid=openid[:8] + "...",
                phone=normalized_phone,
                ip=client_ip,
            )

        if not binding_created and needs_commit:
            await db.commit()
            if binding_obj:
                await db.refresh(binding_obj)

        if not await user_crud.is_active(user):
            await _record_login_attempt(
                db,
                user=user,
                login_type=LoginType.WECHAT,
                platform=DeviceType.MINI_PROGRAM,
                device_id=body.device_id,
                result=LoginResult.FAIL,
                fail_reason="ACCOUNT_INACTIVE",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            logger.warning("wechat_login_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        token_pair = await _issue_jwt_token_for_user(
            db,
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
            log_event="wechat_token_created",
            device_type=DeviceType.MINI_PROGRAM,
            device_id=body.device_id,
        )
        await _record_login_attempt(
            db,
            user=user,
            login_type=LoginType.WECHAT,
            platform=DeviceType.MINI_PROGRAM,
            device_id=body.device_id,
            result=LoginResult.SUCCESS,
            fail_reason=None,
            user_token_id=token_pair.user_token_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        profile = await _ensure_profile_stub(db, user=user)
        avatar_url = await get_avatar_url(profile)

        message: str | None = None
        if created_new_user:
            message = "注册成功"
        elif replaced_old_wechat:
            message = "已用该手机号的账号登录并完成微信绑定"

        logger.info(
            "wechat_bind_success",
            user_id=user.id,
            phone=normalized_phone,
            openid=openid[:8] + "...",
            ip=client_ip,
        )

        return WeChatBindPhoneResponse(
            status="success",
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            needs_profile_setup=bool(user.needs_profile_setup),
            user=_build_user_payload(user, profile, avatar_url),
            message=message,
            binding_reused=binding_reused,
            replaced_old_wechat=replaced_old_wechat,
        )

    except WeChatAPIError as e:
        logger.error(
            "wechat_api_error",
            errcode=e.errcode,
            errmsg=e.errmsg,
            ip=client_ip,
        )
        raise HTTPException(status_code=500, detail="系统错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error("wechat_bind_phone_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/wechat/refresh-phone", response_model=WeChatRefreshPhoneResponse)
async def refresh_wechat_phone(
    request: Request,
    body: WeChatRefreshPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeChatRefreshPhoneResponse:
    """Refresh bound phone number via WeChat authorization for authenticated users."""
    client_ip = _get_client_ip(request)
    wechat_client = WeChatClient()

    try:
        access_token = await wechat_client.get_access_token()
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]
        unionid = session_data.get("unionid")

        logger.info(
            "wechat_refresh_code2session_success",
            openid=openid[:8] + "...",
            qiao_id=current_user.qiao_id,
            ip=client_ip,
        )

        existing_binding = await user_auth_crud.get_by_provider_uid(
            db, auth_type=AuthType.WECHAT, provider_uid=openid
        )

        if existing_binding and existing_binding.user_id != current_user.id:
            logger.warning(
                "wechat_refresh_binding_conflict",
                openid=openid[:8] + "...",
                current_qiao_id=current_user.qiao_id,
                bound_user_id=existing_binding.user_id,
                ip=client_ip,
            )
            raise HTTPException(status_code=409, detail="此微信已关联其他账号")

        if not existing_binding:
            await user_auth_crud.create_binding(
                db,
                user_id=current_user.id,
                user_qiao_id=current_user.qiao_id,
                auth_type=AuthType.WECHAT,
                provider_uid=openid,
                unionid=unionid,
            )
            logger.info(
                "wechat_refresh_binding_created",
                qiao_id=current_user.qiao_id,
                openid=openid[:8] + "...",
                ip=client_ip,
            )

        phone_data = await wechat_client.get_phone_number(body.phone_code, access_token)
        phone_info = await _apply_wechat_phone_mock(
            db,
            phone_data.get("phone_info", {}),
        )
        country_code = phone_info.get("countryCode")
        pure_phone = phone_info.get("purePhoneNumber")

        try:
            phone_e164 = f"+{country_code}{pure_phone}"
        except Exception:
            logger.warning(
                "wechat_refresh_phone_format_error",
                openid=openid[:8] + "...",
                qiao_id=current_user.qiao_id,
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="暂不支持国际手机号")

        if not is_china_phone(phone_e164):
            logger.warning(
                "wechat_refresh_international_phone",
                openid=openid[:8] + "...",
                qiao_id=current_user.qiao_id,
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="暂不支持国际手机号")

        try:
            normalized_phone = normalize_phone(phone_e164)
        except ValueError as e:
            logger.warning(
                "wechat_refresh_invalid_phone_format",
                openid=openid[:8] + "...",
                phone=pure_phone,
                error=str(e),
                ip=client_ip,
            )
            raise HTTPException(status_code=400, detail="手机号格式无效")

        existing_user = await user_crud.get_by_phone(db, phone=normalized_phone)
        if existing_user and existing_user.id != current_user.id:
            logger.warning(
                "wechat_refresh_phone_in_use",
                openid=openid[:8] + "...",
                phone=normalized_phone,
                qiao_id=current_user.qiao_id,
                ip=client_ip,
            )
            raise HTTPException(status_code=409, detail="该手机号已注册")

        await user_crud.update(db, db_obj=current_user, obj_in={"phone": normalized_phone})
        await db.refresh(current_user)

        logger.info(
            "wechat_refresh_phone_success",
            qiao_id=current_user.qiao_id,
            phone=normalized_phone,
            ip=client_ip,
        )

        profile = await _ensure_profile_stub(db, user=current_user)
        avatar_url = await get_avatar_url(profile)

        return WeChatRefreshPhoneResponse(
            phone=mask_phone(normalized_phone),
            user=_build_user_payload(current_user, profile, avatar_url),
        )

    except WeChatAPIError as e:
        logger.error(
            "wechat_refresh_api_error",
            errcode=e.errcode,
            errmsg=e.errmsg,
            qiao_id=current_user.qiao_id,
            ip=client_ip,
        )
        raise HTTPException(status_code=500, detail="系统错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "wechat_refresh_phone_failed",
            error=str(e),
            qiao_id=current_user.qiao_id,
            ip=client_ip,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_token(
    body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
) -> RefreshTokenResponse:
    """Refresh access token using refresh token."""
    refresh_token = body.refresh_token.strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="登录已失效，请重新登录")

    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    user_token = await token_crud.get_by_refresh_hash(db, refresh_hash=refresh_hash)
    if (
        not user_token
        or user_token.status != 1
        or user_token.refresh_revoked_at is not None
        or not user_token.refresh_expires_at
        or user_token.refresh_expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=401, detail="登录失效")

    _enforce_refresh_rate_limit(refresh_hash)
    access_info = await _rotate_access_token(db, user_token=user_token)

    logger.info(
        "access_token_refreshed",
        qiao_id=user_token.user_qiao_id,
        token_id=user_token.id,
    )

    return RefreshTokenResponse(
        access_token=access_info.access_token,
        expires_in=access_info.expires_in,
    )


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """User logout endpoint.

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
        revoked_token = await token_crud.revoke_access_token(db, token=token)
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
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/phone", response_model=VerifyPhoneResponse)
async def verify_phone(
    request: Request, body: VerifyPhoneRequest, db: AsyncSession = Depends(get_db)
) -> VerifyPhoneResponse:
    """Unified phone verification endpoint (login/registration entry).

    This endpoint handles both login and registration scenarios:
    - If user exists: Direct login, return token and user info
    - If user doesn't exist: Return temporary token for profile setup

    Args:
        request: FastAPI request
        body: Contains phone and sms_code
        db: Database session

    Returns:
        VerifyPhoneResponse with login info or registration token

    Raises:
        HTTPException: 400/500 for various errors

    """
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

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
        _consume_sms_code(normalized_phone, body.sms_code)
        logger.info("verify_phone_sms_verified", phone=normalized_phone, ip=client_ip)

        # 3. Check if user exists or create stub
        user = await user_crud.get_by_phone(db, phone=normalized_phone)
        created_new_user = False

        if not user:
            try:
                user_id = generate_snowflake_id()
                qiao_id = generate_qiao_id()
                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    username=None,  # NULL until user sets it
                    user_type=1,
                    status=1,
                    needs_profile_setup=True,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                created_new_user = True
                logger.info(
                    "verify_phone_user_created",
                    qiao_id=user.qiao_id,
                    phone=normalized_phone,
                    ip=client_ip,
                )
            except Exception as e:
                logger.error(
                    "verify_phone_user_creation_failed",
                    phone=normalized_phone,
                    error=str(e),
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail="系统错误")
        else:
            logger.info(
                "verify_phone_user_exists",
                qiao_id=user.qiao_id,
                phone=normalized_phone,
                ip=client_ip,
            )

        # Check user status
        if not await user_crud.is_active(user):
            await _record_login_attempt(
                db,
                user=user,
                login_type=LoginType.SMS,
                platform=DeviceType.MINI_PROGRAM,
                device_id=body.device_id,
                result=LoginResult.FAIL,
                fail_reason="ACCOUNT_INACTIVE",
                client_ip=client_ip,
                user_agent=user_agent,
            )
            logger.warning("verify_phone_user_inactive", qiao_id=user.qiao_id, ip=client_ip)
            raise HTTPException(status_code=400, detail="账号已被禁用")

        profile = await _ensure_profile_stub(db, user=user)
        avatar_url = await get_avatar_url(profile)

        try:
            token_pair = await _issue_jwt_token_for_user(
                db,
                user=user,
                client_ip=client_ip,
                user_agent=user_agent,
                log_event="verify_phone_token_created",
                device_type=DeviceType.MINI_PROGRAM,
                device_id=body.device_id,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "verify_phone_token_creation_failed",
                qiao_id=user.qiao_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="系统错误")

        if created_new_user:
            logger.info(
                "needs_profile_setup_initial",
                qiao_id=user.qiao_id,
                needs_profile_setup=user.needs_profile_setup,
            )
        await _record_login_attempt(
            db,
            user=user,
            login_type=LoginType.SMS,
            platform=DeviceType.MINI_PROGRAM,
            device_id=body.device_id,
            result=LoginResult.SUCCESS,
            fail_reason=None,
            user_token_id=token_pair.user_token_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return VerifyPhoneResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            needs_profile_setup=bool(user.needs_profile_setup),
            user=_build_user_payload(user, profile, avatar_url),
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("verify_phone_failed", error=str(e), ip=client_ip, exc_info=True)
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/user/verify/send-code", response_model=VerifySendCodeResponse)
async def send_verification_code(
    body: VerifySendCodeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifySendCodeResponse:
    """Send verification code for unified verification mechanism.

    Supports phone and email verification.
    Used for sensitive operations like changing phone/email, resetting password, etc.

    Args:
        body: Verification code request
        request: FastAPI request
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
                provider, captcha_meta = await create_captcha_provider_for_request(
                    "user", db, request
                )
                if not isinstance(provider, NoneCaptchaProvider):
                    if not body.captcha_token:
                        # Ask client to complete CAPTCHA first
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=_protective_denial_detail(
                                reason="VERIFY_SEND_CAPTCHA_REQUIRED",
                                camouflage_message="需要完成人机验证后再试",
                                captcha_metadata=captcha_meta.to_response(),
                            ),
                        )

                    is_valid, error = await provider.verify_token(body.captcha_token, client_ip)
                    if not is_valid:
                        logger.warning("verify_send_code_captcha_failed", error=error)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=_protective_denial_detail(
                                reason="VERIFY_SEND_CAPTCHA_INVALID",
                                camouflage_message="需要完成人机验证后再试",
                                captcha_error=error,
                            ),
                        )
                logger.info("verify_send_code_captcha_verified", user_id=current_user.id)
            except HTTPException:
                raise
            except Exception as e:
                logger.error("verify_send_code_captcha_error", error=str(e), exc_info=True)
                raise HTTPException(status_code=500, detail="系统错误")

            target = body.target if body.target else current_user.phone
            if not target:
                raise HTTPException(status_code=400, detail="请先绑定手机号")

            # Normalize phone
            normalized_phone = normalize_phone(target)

            # Check rate limit (reuse SMS group limits from system config)
            allowed, error_code, retry_after = await check_rate_limit(normalized_phone, "sms", db)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_protective_denial_detail(
                        reason="VERIFY_SEND_SMS_RATE_LIMIT",
                        camouflage_message="请30秒后再试",
                        limiter_error=error_code,
                        retry_after=retry_after,
                    ),
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
                raise HTTPException(status_code=500, detail="系统错误")

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
                raise HTTPException(status_code=400, detail="请先绑定邮箱")

            # TODO: Implement email verification code sending
            # For now, raise not implemented error
            raise HTTPException(status_code=501, detail="系统错误")

        raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "send_verification_code_failed", error=str(e), user_id=current_user.id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="系统错误")


@router.post("/user/verify/confirm", response_model=OperationTokenResponse)
async def confirm_verification_code(
    body: VerifyConfirmRequest,
    current_user: User = Depends(get_current_user),
) -> OperationTokenResponse:
    """Confirm verification code and get operation token.

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
                raise HTTPException(status_code=400, detail="请先绑定手机号")

            normalized_phone = normalize_phone(current_user.phone)

            # Verify code
            if normalized_phone not in _verification_codes:
                raise HTTPException(status_code=400, detail="验证码已失效，请重新获取")

            stored_code, expires_at = _verification_codes[normalized_phone]

            if datetime.now(UTC) >= expires_at:
                del _verification_codes[normalized_phone]
                raise HTTPException(status_code=400, detail="验证码已失效，请重新获取")

            if stored_code != body.code:
                raise HTTPException(status_code=400, detail="验证码有误，请重新输入")

            # Delete used code
            del _verification_codes[normalized_phone]

            # Generate operation token
            operation_token = _generate_operation_token(current_user.id)

            logger.info("verification_confirmed", user_id=current_user.id, verify_type="phone")

            return OperationTokenResponse(operation_token=operation_token, expires_in=300)

        if body.verify_type == "email":
            # TODO: Implement email verification
            raise HTTPException(status_code=501, detail="系统错误")

        raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "confirm_verification_failed", error=str(e), user_id=current_user.id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="系统错误")


def _coerce_int(value: JSONValue | None) -> int | None:
    """Normalize JSONValue into an integer, if possible."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
