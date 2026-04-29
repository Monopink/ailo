"""User profile API endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.account_segment_mapper import resolve_account_segment
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.crud.message import media_file as media_file_crud
from app.crud.profile import profile as profile_crud
from app.crud.profile_logs import write_user_profile_change_logs
from app.crud.user import user as user_crud
from app.enums import FileStatus, ProfileModifierType, ProfileOwnerType
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.schemas.user_profile import (
    MinorModePinRequest,
    MinorModePinUpdateRequest,
    MinorModePinVerifyResponse,
    MinorModeStatusResponse,
    UserAccountResponse,
    UsernameCheckResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.profile.avatar import get_avatar_url
from app.services.profile.region import build_cn_region_snapshot
from app.services.security.rate_limiter import (
    check_username_check_rate_limit,
    check_username_submit_rate_limit,
)
from app.services.security.username import (
    UsernameValidationConfigError,
    UsernameValidationIssue,
    UsernameValidationReason,
    validate_username_or_issue,
)
from app.utils.email import mask_email
from app.utils.logging import get_logger
from app.utils.phone import mask_phone
from app.utils.text_limits import PROFILE_BIO_RULE, PROFILE_NICKNAME_RULE, validate_text_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["User Profile"])

USERNAME_REASON_ALREADY_USED = "USERNAME_ALREADY_USED"
USERNAME_REASON_LOCKED = "USERNAME_LOCKED"
USERNAME_REASON_CHECK_RATE_LIMIT_SHORT = "USERNAME_CHECK_RATE_LIMIT_SHORT"
USERNAME_REASON_CHECK_RATE_LIMIT_LONG = "USERNAME_CHECK_RATE_LIMIT_LONG"
USERNAME_REASON_SUBMIT_RATE_LIMIT = "USERNAME_SUBMIT_RATE_LIMIT"
MINOR_MODE_REASON_PIN_REQUIRED = "MINOR_MODE_PIN_REQUIRED"
MINOR_MODE_REASON_PIN_INVALID = "MINOR_MODE_PIN_INVALID"
MINOR_MODE_REASON_NOT_ENABLED = "MINOR_MODE_NOT_ENABLED"
MINOR_MODE_PIN_LENGTH = 4

USERNAME_MESSAGE_BY_REASON: dict[UsernameValidationReason, str] = {
    UsernameValidationReason.EMPTY: "敲敲号不能为空",
    UsernameValidationReason.LEADING_OR_TRAILING_SPACES: "敲敲号不能以空格开头或结尾",
    UsernameValidationReason.TOO_SHORT: "敲敲号长度不能少于5个字符",
    UsernameValidationReason.TOO_LONG: "敲敲号长度不能超过20个字符",
    UsernameValidationReason.MUST_START_WITH_LETTER: "敲敲号必须以字母开头",
    UsernameValidationReason.INVALID_CHARACTERS: "敲敲号仅支持字母、数字、“_”和“-”",
    UsernameValidationReason.RESERVED: "该敲敲号不可使用",
}


def _build_username_error_detail(*, message: str, reason: str) -> dict[str, str]:
    return {"message": message, "reason": reason}


def _build_minor_mode_error_detail(*, message: str, reason: str) -> dict[str, str]:
    return {"message": message, "reason": reason}


def _raise_username_error(
    *,
    status_code: int,
    message: str,
    reason: str,
    retry_after: int | None = None,
) -> None:
    headers: dict[str, str] | None = None
    if retry_after is not None:
        headers = {"Retry-After": str(retry_after)}
    raise HTTPException(
        status_code=status_code,
        detail=_build_username_error_detail(message=message, reason=reason),
        headers=headers,
    )


def _raise_minor_mode_error(
    *,
    status_code: int,
    message: str,
    reason: str,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_build_minor_mode_error_detail(message=message, reason=reason),
    )


def _validate_minor_mode_pin_or_raise(pin: str) -> str:
    normalized = pin.strip()
    if len(normalized) != MINOR_MODE_PIN_LENGTH or not normalized.isdigit():
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="请输入4位数字密码",
            reason=MINOR_MODE_REASON_PIN_REQUIRED,
        )
    return normalized


def _serialize_minor_mode_status(user: User) -> MinorModeStatusResponse:
    enabled_at = user.minor_mode_enabled_at.isoformat() if user.minor_mode_enabled_at else None
    pin_updated_at = (
        user.minor_mode_pin_updated_at.isoformat() if user.minor_mode_pin_updated_at else None
    )
    return MinorModeStatusResponse(
        enabled=user.minor_mode_enabled,
        has_pin=bool(user.minor_mode_pin_hash),
        enabled_at=enabled_at,
        pin_updated_at=pin_updated_at,
    )


def _validate_profile_update_payload_or_raise(body: UserProfileUpdateRequest) -> None:
    """Validate profile update payload rules that require field-presence semantics."""
    region_fields = {
        "region_country_code",
        "region_cn_city_code",
        "region_province_name",
        "region_city_name",
    }
    if region_fields.intersection(body.model_fields_set):
        if "region_country_code" not in body.model_fields_set:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")

        if body.region_country_code is None:
            required_null_fields = (
                "region_cn_city_code",
                "region_province_name",
                "region_city_name",
            )
            if any(field not in body.model_fields_set for field in required_null_fields):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
            if (
                body.region_cn_city_code is not None
                or body.region_province_name is not None
                or body.region_city_name is not None
            ):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
        else:
            country_code = body.region_country_code.strip().upper()
            if country_code != "CN":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
            if (
                "region_cn_city_code" not in body.model_fields_set
                or "region_province_name" not in body.model_fields_set
                or "region_city_name" not in body.model_fields_set
                or body.region_cn_city_code is None
                or body.region_province_name is None
                or body.region_city_name is None
            ):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
            if not UserProfileUpdateRequest.is_valid_cn_city_code(body.region_cn_city_code):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
            if body.region_province_name.strip() == "" or body.region_city_name.strip() == "":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")
            if (
                build_cn_region_snapshot(
                    province_name=body.region_province_name,
                    city_name=body.region_city_name,
                )
                == ""
            ):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="地区参数错误")

    if "nickname" in body.model_fields_set:
        nickname = body.nickname
        if nickname is None or nickname.strip() == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="昵称不能为空")
        if any(char.isspace() for char in nickname):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="昵称不能包含空格")
        nickname_error = validate_text_limit(nickname, PROFILE_NICKNAME_RULE)
        if nickname_error is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=nickname_error)

    if "bio" in body.model_fields_set and body.bio is not None:
        bio_error = validate_text_limit(body.bio, PROFILE_BIO_RULE)
        if bio_error is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=bio_error)


def _resolve_username_validation_error(issue: UsernameValidationIssue) -> tuple[str, str]:
    message = USERNAME_MESSAGE_BY_REASON.get(issue.reason, "敲敲号格式有误")
    return message, issue.reason.value


async def _check_username_limiter_or_raise(
    *,
    user_id: int,
    db: AsyncSession,
) -> None:
    allowed, reason, retry_after = await check_username_check_rate_limit(str(user_id), db)
    if allowed:
        return

    if reason == USERNAME_REASON_CHECK_RATE_LIMIT_SHORT:
        message = "敲敲号检查过于频繁，请稍后再试"
    elif reason == USERNAME_REASON_CHECK_RATE_LIMIT_LONG:
        message = "敲敲号检查次数过多，请稍后再试"
    else:
        message = "敲敲号检查过于频繁，请稍后再试"

    _raise_username_error(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        message=message,
        reason=reason or USERNAME_REASON_CHECK_RATE_LIMIT_SHORT,
        retry_after=retry_after,
    )


async def _submit_username_limiter_or_raise(
    *,
    user_id: int,
    db: AsyncSession,
) -> None:
    allowed, reason, retry_after = await check_username_submit_rate_limit(str(user_id), db)
    if allowed:
        return
    _raise_username_error(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        message="敲敲号提交过于频繁，请稍后再试",
        reason=reason or USERNAME_REASON_SUBMIT_RATE_LIMIT,
        retry_after=retry_after,
    )


async def _validate_username_or_raise(
    *,
    db: AsyncSession,
    username: str,
) -> None:
    issue = await validate_username_or_issue(db, username)
    if issue is None:
        return
    message, reason = _resolve_username_validation_error(issue)
    _raise_username_error(status_code=status.HTTP_400_BAD_REQUEST, message=message, reason=reason)


async def _ensure_username_unique_or_raise(
    *,
    db: AsyncSession,
    username: str,
    current_user_id: int,
) -> None:
    existing_user = await user_crud.get_by_username(db, username=username)
    if existing_user and existing_user.id != current_user_id:
        _raise_username_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="该用户名已被使用",
            reason=USERNAME_REASON_ALREADY_USED,
        )


async def _ensure_username_available_or_raise(
    *,
    db: AsyncSession,
    username: str,
    current_user_id: int,
) -> None:
    await _validate_username_or_raise(db=db, username=username)
    await _ensure_username_unique_or_raise(
        db=db,
        username=username,
        current_user_id=current_user_id,
    )


async def _update_username_if_needed(
    *,
    body: UserProfileUpdateRequest,
    current_user: User,
    db: AsyncSession,
) -> User:
    if body.username is None:
        return current_user

    current_username = current_user.username
    if current_username is not None:
        _raise_username_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="敲敲号不可修改",
            reason=USERNAME_REASON_LOCKED,
        )

    await _submit_username_limiter_or_raise(user_id=current_user.id, db=db)
    await _ensure_username_available_or_raise(
        db=db,
        username=body.username,
        current_user_id=current_user.id,
    )

    try:
        result = await db.execute(
            sql_update(User)
            .where(User.id == current_user.id, User.username.is_(None))
            .values(username=body.username)
        )
        if result.rowcount != 1:
            _raise_username_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="敲敲号不可修改",
                reason=USERNAME_REASON_LOCKED,
            )
        current_user.username = body.username
        db.add(current_user)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        _raise_username_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="该用户名已被使用",
            reason=USERNAME_REASON_ALREADY_USED,
        )
    return current_user


async def _resolve_avatar_update(
    *,
    body: UserProfileUpdateRequest,
    current_user: User,
    db: AsyncSession,
) -> tuple[str | None, int | None]:
    if body.avatar_file_id is None:
        return None, None

    media_file = await media_file_crud.get_by_file_id(db, file_id=body.avatar_file_id)
    if not media_file:
        raise HTTPException(status_code=404, detail="系统错误")

    if media_file.upload_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="系统错误")

    if media_file.status != int(FileStatus.ACTIVE):
        raise HTTPException(status_code=400, detail="头像文件未激活")

    return media_file.object_key, media_file.id


async def _upsert_profile(
    *,
    body: UserProfileUpdateRequest,
    current_user: User,
    avatar_key: str | None,
    avatar_media_id: int | None,
    db: AsyncSession,
) -> Profile:
    user_profile_before = await profile_crud.get_by_owner(
        db, owner_id=current_user.id, owner_type=ProfileOwnerType.USER
    )

    profile_data = body.model_dump(
        exclude_unset=True,
        exclude={"username", "region_province_name", "region_city_name"},
    )
    if "region_country_code" in profile_data and isinstance(
        profile_data["region_country_code"], str
    ):
        profile_data["region_country_code"] = profile_data["region_country_code"].strip().upper()
    if "region_cn_city_code" in profile_data and isinstance(
        profile_data["region_cn_city_code"], str
    ):
        profile_data["region_cn_city_code"] = profile_data["region_cn_city_code"].strip()
    if "region_country_code" in body.model_fields_set:
        if body.region_country_code is None:
            profile_data["region"] = None
        else:
            profile_data["region"] = build_cn_region_snapshot(
                province_name=body.region_province_name or "",
                city_name=body.region_city_name or "",
            )

    if "avatar_file_id" in profile_data:
        profile_data["avatar_key"] = avatar_key
        profile_data["avatar_media_id"] = avatar_media_id
        del profile_data["avatar_file_id"]

    update_data = ProfileUpdate(**profile_data)
    changed_fields: set[str] = set(profile_data.keys())
    if user_profile_before:
        updated_profile = await profile_crud.update_by_owner(
            db,
            owner_id=current_user.id,
            owner_type=ProfileOwnerType.USER,
            obj_in=update_data,
            commit=False,
        )
        if not updated_profile:
            raise HTTPException(status_code=500, detail="系统错误")
        await write_user_profile_change_logs(
            db,
            before=user_profile_before,
            after=updated_profile,
            changed_fields=changed_fields,
            modified_by_type=ProfileModifierType.USER,
            change_reason="user_profile_update",
        )
        return updated_profile

    create_data = ProfileCreate(**profile_data)
    created_profile = await profile_crud.create_with_owner(
        db,
        obj_in=create_data,
        owner_id=current_user.id,
        owner_qiao_id=current_user.qiao_id,
        owner_type=ProfileOwnerType.USER,
        commit=False,
    )
    await write_user_profile_change_logs(
        db,
        before=None,
        after=created_profile,
        changed_fields=changed_fields,
        modified_by_type=ProfileModifierType.USER,
        change_reason="user_profile_update",
    )
    return created_profile


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
            account_segment=resolve_account_segment(current_user),
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
        raise HTTPException(status_code=500, detail="系统错误") from e


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
        raise HTTPException(status_code=500, detail="系统错误") from e


@router.get("/minor-mode", response_model=MinorModeStatusResponse)
async def get_minor_mode_status(
    current_user: User = Depends(get_current_user),
) -> MinorModeStatusResponse:
    """Get current user's minor mode status."""
    return _serialize_minor_mode_status(current_user)


@router.put("/minor-mode/enable", response_model=MinorModeStatusResponse)
async def enable_minor_mode(
    body: MinorModePinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MinorModeStatusResponse:
    """Enable minor mode and set 4-digit PIN."""
    pin = _validate_minor_mode_pin_or_raise(body.pin)
    now = datetime.now(UTC)
    current_user.minor_mode_enabled = True
    current_user.minor_mode_pin_hash = get_password_hash(pin)
    current_user.minor_mode_enabled_at = now
    current_user.minor_mode_pin_updated_at = now
    current_user.minor_mode_disabled_at = None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    logger.info("minor_mode_enabled", qiao_id=current_user.qiao_id)
    return _serialize_minor_mode_status(current_user)


@router.put("/minor-mode/disable", response_model=MinorModeStatusResponse)
async def disable_minor_mode(
    body: MinorModePinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MinorModeStatusResponse:
    """Disable minor mode and clear PIN hash."""
    pin_hash = current_user.minor_mode_pin_hash
    if not current_user.minor_mode_enabled or pin_hash is None:
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="青少年模式未开启",
            reason=MINOR_MODE_REASON_NOT_ENABLED,
        )
    assert pin_hash is not None
    pin = _validate_minor_mode_pin_or_raise(body.pin)
    if not verify_password(pin, pin_hash):
        logger.info("minor_mode_disable_failed", qiao_id=current_user.qiao_id)
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="密码错误",
            reason=MINOR_MODE_REASON_PIN_INVALID,
        )

    current_user.minor_mode_enabled = False
    current_user.minor_mode_pin_hash = None
    current_user.minor_mode_disabled_at = datetime.now(UTC)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    logger.info("minor_mode_disable_success", qiao_id=current_user.qiao_id)
    return _serialize_minor_mode_status(current_user)


@router.put("/minor-mode/pin", response_model=MinorModeStatusResponse)
async def update_minor_mode_pin(
    body: MinorModePinUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MinorModeStatusResponse:
    """Update minor mode PIN."""
    pin_hash = current_user.minor_mode_pin_hash
    if not current_user.minor_mode_enabled or pin_hash is None:
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="青少年模式未开启",
            reason=MINOR_MODE_REASON_NOT_ENABLED,
        )
    assert pin_hash is not None
    old_pin = _validate_minor_mode_pin_or_raise(body.old_pin)
    new_pin = _validate_minor_mode_pin_or_raise(body.new_pin)
    if not verify_password(old_pin, pin_hash):
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="密码错误",
            reason=MINOR_MODE_REASON_PIN_INVALID,
        )
    current_user.minor_mode_pin_hash = get_password_hash(new_pin)
    current_user.minor_mode_pin_updated_at = datetime.now(UTC)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    logger.info("minor_mode_pin_changed", qiao_id=current_user.qiao_id)
    return _serialize_minor_mode_status(current_user)


@router.post("/minor-mode/pin/verify", response_model=MinorModePinVerifyResponse)
async def verify_minor_mode_pin(
    body: MinorModePinRequest,
    current_user: User = Depends(get_current_user),
) -> MinorModePinVerifyResponse:
    """Verify minor mode PIN for current user."""
    pin_hash = current_user.minor_mode_pin_hash
    if not current_user.minor_mode_enabled or pin_hash is None:
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="青少年模式未开启",
            reason=MINOR_MODE_REASON_NOT_ENABLED,
        )
    assert pin_hash is not None
    pin = _validate_minor_mode_pin_or_raise(body.pin)
    verified = verify_password(pin, pin_hash)
    if not verified:
        _raise_minor_mode_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="密码错误",
            reason=MINOR_MODE_REASON_PIN_INVALID,
        )
    return MinorModePinVerifyResponse(verified=True)


@router.get("/username/check", response_model=UsernameCheckResponse)
async def check_username(
    username: str = Query(..., description="Candidate username"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsernameCheckResponse:
    """Check whether username is valid and available."""
    try:
        if current_user.username is not None:
            _raise_username_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="敲敲号不可修改",
                reason=USERNAME_REASON_LOCKED,
            )
        await _check_username_limiter_or_raise(user_id=current_user.id, db=db)
        await _ensure_username_available_or_raise(
            db=db,
            username=username,
            current_user_id=current_user.id,
        )
        return UsernameCheckResponse(available=True)
    except UsernameValidationConfigError:
        raise HTTPException(status_code=500, detail="系统错误")


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
        _validate_profile_update_payload_or_raise(body)

        current_user = await _update_username_if_needed(
            body=body,
            current_user=current_user,
            db=db,
        )

        avatar_key, avatar_media_id = await _resolve_avatar_update(
            body=body,
            current_user=current_user,
            db=db,
        )
        updated_profile = await _upsert_profile(
            body=body,
            current_user=current_user,
            avatar_key=avatar_key,
            avatar_media_id=avatar_media_id,
            db=db,
        )

        # Generate avatar URL dynamically
        avatar_url = await get_avatar_url(updated_profile)

        if current_user.needs_profile_setup:
            current_user.needs_profile_setup = False
            db.add(current_user)
            logger.info("needs_profile_setup_cleared", qiao_id=current_user.qiao_id)

        await db.commit()

        # Build response
        response = UserProfileResponse(
            qiao_id=current_user.qiao_id,
            account_segment=resolve_account_segment(current_user),
            username=current_user.username,
            nickname=updated_profile.nickname,
            gender=updated_profile.gender,
            avatar_url=avatar_url,
            bio=updated_profile.bio,
            region=updated_profile.region,
        )

        logger.info("user_profile_updated", qiao_id=current_user.qiao_id)

        return response

    except UsernameValidationConfigError:
        raise HTTPException(status_code=500, detail="系统错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "update_user_profile_failed", error=str(e), qiao_id=current_user.qiao_id, exc_info=True
        )
        raise HTTPException(status_code=500, detail="系统错误") from e
