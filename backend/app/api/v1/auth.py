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
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.account_segment_mapper import resolve_account_segment
from app.core.config import get_settings
from app.core.database import get_db
from app.crud.user import login_record as login_record_crud
from app.crud.user import user as user_crud
from app.crud.user import user_auth as user_auth_crud
from app.crud.user import user_token as token_crud
from app.enums import AuthType, DetectionSource, DeviceType, LoginResult, LoginType, ReviewScope
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
from app.services.entitlement.service import ensure_system_initial_ai_contact_limit
from app.services.profile.avatar import get_avatar_url
from app.services.profile.integrity import ensure_user_profile
from app.services.review_scope_classifier import classify_runtime_review_scope
from app.services.security import SecurityRequestContext, enforce_attack_scan, is_ip_blocked
from app.services.security.auth_tracker import check_lockout, record_auth_failure, reset_failures
from app.services.security.rate_limiter import check_password_login_rate_limit, check_rate_limit
from app.services.security.sms.factory import create_sms_provider
from app.services.system_config import get_config, get_config_int
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
DEFAULT_NICKNAME_PREFIX_KEY = "default_nickname_prefix"
DEFAULT_NICKNAME_SUFFIX_LENGTH_KEY = "default_nickname_suffix_length"
DEFAULT_NICKNAME_SUFFIX_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Format: phone -> (code, expires_at)
_verification_codes: dict[str, tuple[str, datetime]] = {}

# Format: token -> (user_id, expires_at)
_operation_tokens: dict[str, tuple[int, datetime]] = {}

# Constants
SMS_COOLDOWN_SECONDS = 60
SMS_CODE_LENGTH_DIGITS = 6
OPERATION_TOKEN_TTL_SECONDS = 5 * 60  # 5 minutes

_refresh_token_requests: dict[str, list[datetime]] = {}
REFRESH_RATE_LIMIT = 5
REFRESH_RATE_WINDOW = timedelta(minutes=1)


async def _get_sms_code_ttl_seconds(db: AsyncSession) -> int:
    ttl_seconds = await get_config_int(db, key="sms_code_expires_in_seconds")
    if ttl_seconds < 1:
        raise ValueError("sms_code_expires_in_seconds must be >= 1")
    return ttl_seconds


async def _get_sms_code_length_digits(db: AsyncSession) -> int:
    _ = db
    return SMS_CODE_LENGTH_DIGITS


def _generate_numeric_code(length: int) -> str:
    if length < 1:
        raise ValueError("Code length must be >= 1")

    if length == 1:
        return str(secrets.randbelow(10))

    first_digit = str(secrets.randbelow(9) + 1)
    remaining = "".join(str(secrets.randbelow(10)) for _ in range(length - 1))
    return f"{first_digit}{remaining}"


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


def _get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_value = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
    if isinstance(header_value, str) and header_value.strip():
        request_id = header_value.strip()
    else:
        request_id = f"req_{uuid4().hex[:12]}"
    request.state.request_id = request_id
    return request_id


async def _guard_auth_attack(
    request: Request,
    *,
    db: AsyncSession,
    user: User | None,
    fields: dict[str, str],
    detection_source: DetectionSource,
) -> None:
    client_ip = _get_client_ip(request)
    request_id = _get_request_id(request)
    if await is_ip_blocked(db, client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_protective_denial_detail(
                reason="IP_BLOCKED",
                camouflage_message="登录失败，请稍后再试",
                risk_rule_id="security_ip_block",
                request_id=request_id,
            ),
        )

    match = await enforce_attack_scan(
        db,
        context=SecurityRequestContext(
            detection_source=detection_source,
            request_method=request.method,
            request_path=request.url.path,
            client_ip=client_ip,
            request_id=request_id,
            user_id=int(user.id) if user is not None else None,
            user_qiao_id=user.qiao_id if user is not None else None,
        ),
        fields=fields,
        extra_evidence={"layer": "auth_api"},
    )
    if match is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_protective_denial_detail(
                reason="ATTACK_DETECTED",
                camouflage_message="登录失败，请稍后再试",
                risk_rule_id=match.rule_code,
                internal_risk_code=match.rule_code,
                request_id=request_id,
                rule_code=match.rule_code,
                field_name=match.field_name,
            ),
        )


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
    expires_in_days = await get_config_int(db, key="jwt_token_expires_in_days")
    if expires_in_days < 1:
        logger.error("jwt_expiration_config_invalid", value=expires_in_days)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    return expires_in_days * 86400


async def _get_refresh_token_expiration_days(db: AsyncSession) -> int:
    """Return refresh token expiration duration in days."""
    days = await get_config_int(db, key="refresh_token_expires_in_days")
    if days < 1:
        logger.error("refresh_token_expiration_invalid", value=days)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统错误",
        )
    return days


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

    enabled_value = await get_config(db, key=WECHAT_PHONE_MOCK_ENABLED_KEY, required=False)
    if isinstance(enabled_value, bool):
        enabled = enabled_value
    elif isinstance(enabled_value, str):
        enabled = enabled_value.strip().lower() in {"true", "1", "yes", "on"}
    elif enabled_value is None:
        enabled = False
    else:
        enabled = bool(enabled_value)
    if not enabled:
        return phone_info

    pure_phone = phone_info.get("purePhoneNumber")
    if not pure_phone or pure_phone not in WECHAT_TEST_PHONE_NUMBERS:
        return phone_info

    mock_phone = await get_config(db, key=WECHAT_PHONE_MOCK_NUMBER_KEY, required=False)
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
    expires_at = datetime.now(UTC) + timedelta(seconds=OPERATION_TOKEN_TTL_SECONDS)
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
    await _guard_auth_attack(
        request,
        db=db,
        user=None,
        fields={
            "identifier": body.identifier,
            "password": body.password,
            "device_id": str(body.device_id),
            "device_type": str(int(body.device_type)),
        },
        detection_source=DetectionSource.API_AUTH,
    )

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
            detail="账号状态异常",
        )

    await reset_failures(auth_identifier, "user_auth")
    _apply_login_review_scope_upgrade(user=user, user_agent=user_agent)

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
    resolved_nickname = nickname.strip() if isinstance(nickname, str) else ""
    if resolved_nickname == "":
        resolved_nickname = await _build_default_nickname(db)

    profile_in = ProfileCreate(
        nickname=resolved_nickname,
        avatar_key=None,
        avatar_media_id=None,
    )

    profile = await ensure_user_profile(
        db,
        user_id=user.id,
        user_qiao_id=user.qiao_id,
        source="auth._ensure_profile_stub",
        commit=False,
        profile_in=profile_in,
    )
    logger.info("profile_stub_created", qiao_id=user.qiao_id)
    return profile


async def _build_default_nickname(db: AsyncSession) -> str:
    """Build default nickname from system configs."""
    prefix_value = await get_config(db, key=DEFAULT_NICKNAME_PREFIX_KEY, required=True)
    if not isinstance(prefix_value, str):
        raise TypeError(f"{DEFAULT_NICKNAME_PREFIX_KEY} must be a string")
    prefix = prefix_value.strip()
    if prefix == "":
        raise ValueError(f"{DEFAULT_NICKNAME_PREFIX_KEY} must not be empty")

    suffix_length = await get_config_int(db, key=DEFAULT_NICKNAME_SUFFIX_LENGTH_KEY, required=True)
    if suffix_length < 1:
        raise ValueError(f"{DEFAULT_NICKNAME_SUFFIX_LENGTH_KEY} must be >= 1")

    suffix = "".join(secrets.choice(DEFAULT_NICKNAME_SUFFIX_CHARSET) for _ in range(suffix_length))
    return f"{prefix}{suffix}"


def _build_user_payload(
    user: User, profile: Profile | None, avatar_url: str
) -> dict[str, JSONValue]:
    """Construct user payload for authentication responses."""
    return {
        "qiao_id": user.qiao_id,
        "account_segment": resolve_account_segment(user),
        "phone": user.phone,
        "nickname": profile.nickname if profile else None,
        "gender": profile.gender if profile else None,
        "avatar_url": avatar_url,
        "bio": profile.bio if profile else None,
    }


def _resolve_new_mp_user_review_scope(user_agent: str | None) -> int:
    """Resolve review scope for newly registered mini-program users."""
    decision = classify_runtime_review_scope(user_agent)
    if decision.is_limited_scope:
        return int(ReviewScope.MP_WEIXIN_REVIEW)
    return int(ReviewScope.NON_REVIEW)


def _apply_login_review_scope_upgrade(
    *,
    user: User,
    user_agent: str | None,
) -> None:
    """Apply one-way review-scope upgrade for login flows."""
    if int(user.review_scope) == int(ReviewScope.MP_WEIXIN_REVIEW):
        return
    decision = classify_runtime_review_scope(user_agent)
    if not decision.is_limited_scope:
        return
    user.review_scope = int(ReviewScope.MP_WEIXIN_REVIEW)
    logger.info(
        "user_review_scope_upgraded_by_runtime_ua",
        user_id=int(user.id),
        qiao_id=user.qiao_id,
        matched_features=list(decision.matched_features),
    )


class SendSMSRequest(BaseModel):
    """Request model for sending SMS verification code."""

    phone: str = Field(..., description="Phone number (11 digits)")


class SendSMSResponse(BaseModel):
    """Response model for sending SMS."""

    expires_in: int = Field(..., description="Verification code TTL in seconds")
    cooldown_seconds: int = Field(..., description="Cooldown before next send in seconds")


@router.post("/send-sms", response_model=SendSMSResponse)
async def send_sms_code(
    body: SendSMSRequest, db: AsyncSession = Depends(get_db)
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

    try:
        ttl_seconds = await _get_sms_code_ttl_seconds(db)
        digits = await _get_sms_code_length_digits(db)
    except Exception as exc:
        logger.error("sms_code_config_error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="系统配置异常") from exc

    # 3. Generate verification code
    code = _generate_numeric_code(digits)

    # 4. Store code in memory with expiration (for MVP)
    # In production, use Redis with TTL instead
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
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

    return SendSMSResponse(expires_in=ttl_seconds, cooldown_seconds=SMS_COOLDOWN_SECONDS)


@router.post("/wechat/login", response_model=WeChatLoginResponse)
async def wechat_login(
    request: Request, body: WeChatLoginRequest, db: AsyncSession = Depends(get_db)
) -> WeChatLoginResponse:
    """WeChat Mini Program login stage 1: openid check only."""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    await _guard_auth_attack(
        request,
        db=db,
        user=None,
        fields={
            "login_code": body.login_code,
            "device_id": str(body.device_id),
        },
        detection_source=DetectionSource.API_AUTH,
    )
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
            raise HTTPException(status_code=400, detail="账号状态异常")

        _apply_login_review_scope_upgrade(user=user, user_agent=user_agent)
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


async def _resolve_wechat_bind_phone_info(
    db: AsyncSession,
    wechat_client: WeChatClient,
    body: WeChatBindPhoneRequest,
    session_data: dict[str, str],
) -> JSONDict:
    """Resolve phone_info from either new or legacy getPhoneNumber payload."""
    if body.phone_code and body.phone_code.strip():
        access_token = await wechat_client.get_access_token()
        phone_data = await wechat_client.get_phone_number(body.phone_code, access_token)
        logger.info("wechat_bind_phone_protocol_resolved", protocol="code")
        raw_phone_info = phone_data.get("phone_info", {})
    else:
        try:
            decrypted = wechat_client.decrypt_user_data(
                body.encrypted_data or "",
                body.iv or "",
                session_data["session_key"],
            )
        except WeChatAPIError:
            raise HTTPException(status_code=400, detail="请求参数错误")
        logger.info("wechat_bind_phone_protocol_resolved", protocol="encrypted_data")

        watermark = decrypted.get("watermark")
        if isinstance(watermark, dict):
            appid = watermark.get("appid")
            if isinstance(appid, str) and appid and appid != settings.WECHAT_APP_ID:
                logger.warning("wechat_bind_watermark_appid_mismatch", appid=appid)
                raise HTTPException(status_code=400, detail="请求参数错误")

        candidate = decrypted.get("phone_info")
        raw_phone_info = candidate if isinstance(candidate, dict) else decrypted

    if not isinstance(raw_phone_info, dict):
        raise HTTPException(status_code=400, detail="请求参数错误")
    return await _apply_wechat_phone_mock(db, raw_phone_info)


@router.post("/wechat/bind-phone", response_model=WeChatBindPhoneResponse)
async def bind_wechat_phone(
    request: Request, body: WeChatBindPhoneRequest, db: AsyncSession = Depends(get_db)
) -> WeChatBindPhoneResponse:
    """WeChat Mini Program login stage 2: bind phone and issue tokens."""
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    await _guard_auth_attack(
        request,
        db=db,
        user=None,
        fields={
            "login_code": body.login_code,
            "phone_code": body.phone_code or "",
            "encrypted_data": body.encrypted_data or "",
            "iv": body.iv or "",
            "device_id": str(body.device_id),
        },
        detection_source=DetectionSource.API_AUTH,
    )
    wechat_client = WeChatClient()

    try:
        session_data = await wechat_client.code2session(body.login_code)
        openid = session_data["openid"]
        unionid = session_data.get("unionid")

        logger.info(
            "wechat_bind_code2session_success",
            openid=openid[:8] + "...",
            unionid=(unionid[:8] + "..." if unionid else None),
            ip=client_ip,
        )

        phone_info = await _resolve_wechat_bind_phone_info(
            db,
            wechat_client,
            body,
            session_data,
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
                review_scope = _resolve_new_mp_user_review_scope(user_agent)

                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    username=None,
                    user_type=1,
                    review_scope=review_scope,
                    status=1,
                    needs_profile_setup=True,
                )

                db.add(user)
                await db.flush()
                await ensure_system_initial_ai_contact_limit(db, user_id=user.id)
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
            raise HTTPException(status_code=400, detail="账号状态异常")

        _apply_login_review_scope_upgrade(user=user, user_agent=user_agent)
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
    await _guard_auth_attack(
        request,
        db=db,
        user=current_user,
        fields={
            "login_code": body.login_code,
            "phone_code": body.phone_code,
        },
        detection_source=DetectionSource.API_AUTH,
    )
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
    request: Request,
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> RefreshTokenResponse:
    """Refresh access token using refresh token."""
    await _guard_auth_attack(
        request,
        db=db,
        user=None,
        fields={"refresh_token": body.refresh_token},
        detection_source=DetectionSource.API_AUTH,
    )
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
    await _guard_auth_attack(
        request,
        db=db,
        user=None,
        fields={
            "phone": body.phone,
            "sms_code": body.sms_code,
            "device_id": str(body.device_id),
        },
        detection_source=DetectionSource.API_AUTH,
    )

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

        sms_verify_identifiers = (
            f"phone:{normalized_phone}",
            f"ip_phone:{client_ip}:{normalized_phone}",
        )
        for sms_verify_identifier in sms_verify_identifiers:
            allowed, error_code, retry_after = await check_rate_limit(
                sms_verify_identifier,
                "sms_verify",
                db,
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=_protective_denial_detail(
                        reason="SMS_VERIFY_RATE_LIMIT",
                        camouflage_message="验证码校验过于频繁，请稍后再试",
                        limiter_error=error_code,
                        retry_after=retry_after,
                    ),
                )

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
                review_scope = _resolve_new_mp_user_review_scope(user_agent)
                user = User(
                    id=user_id,
                    qiao_id=qiao_id,
                    phone=normalized_phone,
                    username=None,  # NULL until user sets it
                    user_type=1,
                    review_scope=review_scope,
                    status=1,
                    needs_profile_setup=True,
                )
                db.add(user)
                await db.flush()
                await ensure_system_initial_ai_contact_limit(db, user_id=user.id)
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

        _apply_login_review_scope_upgrade(user=user, user_agent=user_agent)
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
            raise HTTPException(status_code=400, detail="账号状态异常")

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

            try:
                ttl_seconds = await _get_sms_code_ttl_seconds(db)
                digits = await _get_sms_code_length_digits(db)
            except Exception as exc:
                logger.error(
                    "verify_send_sms_code_config_error",
                    error=str(exc),
                    user_id=current_user.id,
                    exc_info=True,
                )
                raise HTTPException(status_code=500, detail="系统配置异常") from exc

            # Generate verification code
            code = _generate_numeric_code(digits)

            # Store code
            expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
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

            return VerifySendCodeResponse(cooldown=SMS_COOLDOWN_SECONDS)

        if body.verify_type == "email":
            target = body.target if body.target else current_user.email
            if not target:
                raise HTTPException(status_code=400, detail="请先绑定邮箱")

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

            return OperationTokenResponse(
                operation_token=operation_token,
                expires_in=OPERATION_TOKEN_TTL_SECONDS,
            )

        if body.verify_type == "email":
            raise HTTPException(status_code=501, detail="系统错误")

        raise HTTPException(status_code=400, detail="不支持的验证类型")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "confirm_verification_failed", error=str(e), user_id=current_user.id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="系统错误")
