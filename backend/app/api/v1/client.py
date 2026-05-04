"""Client runtime preflight and observation endpoints."""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.database import get_db
from app.enums import DetectionSource, ReviewScope
from app.exceptions.error_codes import build_protective_denial_detail
from app.models.user import User
from app.services.review_scope_build_cycle import (
    classify_mp_weixin_review_scope_by_build_cycle,
    load_mp_weixin_review_cycle_config,
)
from app.services.security import SecurityRequestContext, enforce_attack_scan, is_ip_blocked
from app.services.security.rate_limiter import check_rate_limit
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)

router = APIRouter(prefix="/client", tags=["Client"])

CLIENT_TYPE_MP_WEIXIN = "mp_weixin"
RUNTIME_EVENT_NAME_WHITELIST: frozenset[str] = frozenset(
    {
        "boot_route_decision",
        "preflight_probe_result",
        "preview_guard_redirect",
        "login_clipboard_intake",
        "invite_intake_attempt",
        "runtime_session_tick",
    }
)
UAFetchStatusValue = int
type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type JsonObject = dict[str, JsonValue]
CLIPBOARD_TEXT_MAX_LENGTH = 2048
TEXT_FIELD_MAX_LENGTH = 4096
MAX_SANITIZE_DEPTH = 8
MAX_LIST_LENGTH = 40
MAX_DICT_KEYS = 40
RATE_LIMIT_WINDOW_SECONDS = 5.0
RATE_LIMIT_WINDOW_MAX = 10
RATE_LIMIT_DAY_SECONDS = 86400.0
RATE_LIMIT_DAY_MAX = 500
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_RUNTIME_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_\-]{1,64}$")
_RUNTIME_PAGE_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9/_\-.]{0,254}$")
_RUNTIME_ENTRY_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9:_\-]{1,64}$")


class _InMemoryWindowLimiter:
    """In-memory limiter for short-window and day-window quotas."""

    def __init__(self) -> None:
        self._short_window: dict[str, deque[float]] = {}
        self._day_window: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, bucket: dict[str, deque[float]], now_ts: float, window_seconds: float) -> None:
        stale_keys: list[str] = []
        threshold = now_ts - window_seconds
        for cache_key, timestamps in bucket.items():
            while timestamps and timestamps[0] < threshold:
                timestamps.popleft()
            if len(timestamps) == 0:
                stale_keys.append(cache_key)
        for cache_key in stale_keys:
            del bucket[cache_key]

    def is_limited(self, key_prefix: str) -> bool:
        now_ts = time.time()
        with self._lock:
            self._prune(self._short_window, now_ts, RATE_LIMIT_WINDOW_SECONDS)
            self._prune(self._day_window, now_ts, RATE_LIMIT_DAY_SECONDS)

            short_timestamps = self._short_window.setdefault(key_prefix, deque())
            day_timestamps = self._day_window.setdefault(key_prefix, deque())
            if len(short_timestamps) >= RATE_LIMIT_WINDOW_MAX:
                return True
            if len(day_timestamps) >= RATE_LIMIT_DAY_MAX:
                return True

            short_timestamps.append(now_ts)
            day_timestamps.append(now_ts)
            return False


runtime_limiter = _InMemoryWindowLimiter()


class ClientHealthResponse(BaseModel):
    """Response payload for client runtime health probe."""

    status: str = Field(..., description="Service availability status")
    server_time_ms: int = Field(..., description="Current server UTC epoch milliseconds")


class PreflightProbeRequest(BaseModel):
    """Runtime preflight probe payload."""

    client_type: str = Field(..., min_length=1, max_length=32)
    device_id: str = Field("", max_length=64)
    user_agent: str = Field("", max_length=2048)
    platform: str = Field("", max_length=32)
    os_version: str = Field("", max_length=64)
    app_version: str = Field("", max_length=32)
    build_id: str = Field("", max_length=64)
    build_time: str | None = Field(None, max_length=64)
    occurred_at_ms: int = Field(..., ge=0)


class PreflightProbeResponse(BaseModel):
    """Runtime preflight probe response."""

    segment_type: int = Field(..., description="Audience segment: 0=standard, 1=limited")
    server_time_ms: int = Field(..., description="Current server UTC epoch milliseconds")


class RuntimeObservationPayload(BaseModel):
    """Runtime observation payload."""

    client_type: str = Field(..., min_length=1, max_length=32)
    device_id: str = Field("", max_length=64)
    session_id: str = Field("", max_length=64)
    user_agent: str = Field("", max_length=2048)
    platform: str = Field("", max_length=32)
    os_version: str = Field("", max_length=64)
    app_version: str = Field("", max_length=32)
    build_id: str = Field("", max_length=64)
    build_time: str | None = Field(None, max_length=64)
    network_type: str = Field("", max_length=32)
    segment_type: int = Field(0, ge=0, le=1)
    matched_features: list[str] = Field(default_factory=list)
    ua_fetch_status: UAFetchStatusValue = Field(0, ge=0, le=3)
    event_name: str = Field(..., min_length=1, max_length=64)
    page_path: str = Field("", max_length=255)
    entry_source: str = Field("", max_length=64)
    event_payload: JsonObject = Field(default_factory=dict)
    request_id: str = Field("", max_length=128)
    occurred_at_ms: int = Field(..., ge=0)


class RuntimeObservationResponse(BaseModel):
    """Acknowledgement for runtime observation ingestion."""

    accepted: bool
    event_id: int


def _normalize_optional_time_string(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if raw == "":
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed


def _normalize_text(value: str, *, max_length: int = TEXT_FIELD_MAX_LENGTH) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    stripped = _CONTROL_CHARS_PATTERN.sub("", normalized)
    return stripped[:max_length]


def _sanitize_json_value(value: object, *, depth: int = 0) -> JsonValue:
    if depth >= MAX_SANITIZE_DEPTH:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        return [_sanitize_json_value(item, depth=depth + 1) for item in value[:MAX_LIST_LENGTH]]
    if isinstance(value, dict):
        sanitized: JsonObject = {}
        for count, (raw_key, raw_value) in enumerate(value.items()):
            if count >= MAX_DICT_KEYS:
                break
            key = _normalize_text(str(raw_key), max_length=64)
            sanitized[key] = _sanitize_json_value(raw_value, depth=depth + 1)
        return sanitized
    return _normalize_text(str(value))


def _sanitize_event_payload(payload: JsonObject) -> JsonObject:
    sanitized = _sanitize_json_value(payload)
    if not isinstance(sanitized, dict):
        return {}

    clipboard_value: str | None = None
    clipboard_text = sanitized.get("clipboard_text")
    if isinstance(clipboard_text, str):
        clipboard_value = clipboard_text
    else:
        clipboard_raw_text = sanitized.get("clipboard_raw_text")
        if isinstance(clipboard_raw_text, str):
            clipboard_value = clipboard_raw_text
    if clipboard_value is not None:
        sanitized["clipboard_text"] = clipboard_value[:CLIPBOARD_TEXT_MAX_LENGTH]
        sanitized.pop("clipboard_raw_text", None)
    return sanitized


def _stable_payload_digest(payload: JsonObject) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_feature_hits(raw_features: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for feature in raw_features:
        value = _normalize_text(feature.strip().lower(), max_length=64)
        if value == "" or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _is_uuid(value: str) -> bool:
    return _UUID_PATTERN.fullmatch(value) is not None


def _is_valid_runtime_session_id(value: str) -> bool:
    return _RUNTIME_SESSION_ID_PATTERN.fullmatch(value) is not None


def _is_valid_runtime_page_path(value: str) -> bool:
    return _RUNTIME_PAGE_PATH_PATTERN.fullmatch(value) is not None


def _is_valid_runtime_entry_source(value: str) -> bool:
    return _RUNTIME_ENTRY_SOURCE_PATTERN.fullmatch(value) is not None


def _safe_client_ip(request: Request) -> str:
    try:
        return get_client_ip(request)
    except ClientIPResolutionError:
        return ""


def _new_request_id(request: Request) -> str:
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


async def _guard_runtime_attack(
    request: Request,
    *,
    db: AsyncSession,
    user: User | None,
    fields: dict[str, str],
    detection_source: DetectionSource,
    request_path: str,
) -> str:
    client_ip = _safe_client_ip(request)
    request_id = _new_request_id(request)
    if client_ip != "" and await is_ip_blocked(db, client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_protective_denial_detail(
                reason="IP_BLOCKED",
                camouflage_message="请求来源受限",
                risk_rule_id="security_ip_block",
                metadata={"request_id": request_id},
            ),
        )

    match = await enforce_attack_scan(
        db,
        context=SecurityRequestContext(
            detection_source=detection_source,
            request_method=request.method,
            request_path=request_path,
            client_ip=client_ip,
            request_id=request_id,
            user_id=int(user.id) if user is not None else None,
            user_qiao_id=str(user.qiao_id) if user is not None else None,
        ),
        fields=fields,
        extra_evidence={"layer": "client_api"},
    )
    if match is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_protective_denial_detail(
                reason="ATTACK_DETECTED",
                camouflage_message="请求来源受限",
                risk_rule_id=match.rule_code,
                internal_risk_code=match.rule_code,
                metadata={
                    "request_id": request_id,
                    "rule_code": match.rule_code,
                    "field_name": match.field_name,
                },
            ),
        )
    return request_id


def _build_runtime_limit_keys(
    *, client_ip: str, device_id: str, session_id: str
) -> tuple[str, ...]:
    keys: list[str] = []
    if client_ip != "":
        keys.append(f"ip:{client_ip}")
    if device_id != "":
        keys.append(f"device:{device_id}")
    if session_id != "":
        keys.append(f"session:{session_id}")
    return tuple(keys)


def _is_runtime_rate_limited(*, client_ip: str, device_id: str, session_id: str) -> bool:
    limit_keys = _build_runtime_limit_keys(
        client_ip=client_ip,
        device_id=device_id,
        session_id=session_id,
    )
    return any(runtime_limiter.is_limited(limit_key) for limit_key in limit_keys)


async def _is_security_rate_limited(
    *,
    db: AsyncSession,
    group: str,
    identifiers: tuple[str, ...],
) -> bool:
    for identifier in identifiers:
        if identifier == "":
            continue
        allowed, _error_code, _retry_after = await check_rate_limit(identifier, group, db)
        if not allowed:
            return True
    return False


@router.get("/health", response_model=ClientHealthResponse)
async def client_health() -> ClientHealthResponse:
    """Lightweight health probe used by mini-program startup flow."""
    return ClientHealthResponse(
        status="ok",
        server_time_ms=int(datetime.now(UTC).timestamp() * 1000),
    )


@router.post("/preflight-probe", response_model=PreflightProbeResponse)
async def preflight_probe(
    request: Request,
    payload: PreflightProbeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> PreflightProbeResponse:
    """Classify runtime segment using build-cycle based reviewer detection."""
    await _guard_runtime_attack(
        request,
        db=db,
        user=current_user,
        fields={
            "client_type": payload.client_type,
            "device_id": payload.device_id,
            "user_agent": payload.user_agent,
            "platform": payload.platform,
            "os_version": payload.os_version,
            "app_version": payload.app_version,
            "build_id": payload.build_id,
        },
        detection_source=DetectionSource.API_RUNTIME,
        request_path=request.url.path,
    )
    client_type = payload.client_type.strip()
    device_id = _normalize_text(payload.device_id.strip(), max_length=64).lower()
    if client_type != CLIENT_TYPE_MP_WEIXIN or not _is_uuid(device_id):
        raise HTTPException(status_code=400, detail="请求参数错误")

    if current_user is not None and int(current_user.review_scope) == int(
        ReviewScope.MP_WEIXIN_REVIEW
    ):
        return PreflightProbeResponse(
            segment_type=1,
            server_time_ms=int(datetime.now(UTC).timestamp() * 1000),
        )

    client_ip = _safe_client_ip(request)
    if await _is_security_rate_limited(
        db=db,
        group="runtime_preflight_probe",
        identifiers=(
            f"ip:{client_ip}" if client_ip != "" else "",
            f"device:{device_id}",
        ),
    ):
        return PreflightProbeResponse(
            segment_type=0,
            server_time_ms=int(datetime.now(UTC).timestamp() * 1000),
        )

    review_cycle_config = await load_mp_weixin_review_cycle_config(db)
    decision = classify_mp_weixin_review_scope_by_build_cycle(
        config=review_cycle_config,
        build_id=payload.build_id,
        build_time=payload.build_time,
        user_agent=payload.user_agent,
        client_ip=client_ip,
    )
    return PreflightProbeResponse(
        segment_type=1 if decision.is_limited_scope else 0,
        server_time_ms=int(datetime.now(UTC).timestamp() * 1000),
    )


@router.post(
    "/runtime-observations",
    response_model=RuntimeObservationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def report_runtime_observation(  # noqa: PLR0911
    request: Request,
    payload: RuntimeObservationPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> RuntimeObservationResponse:
    """Persist runtime environment and behavior observations from mini-program clients."""
    await _guard_runtime_attack(
        request,
        db=db,
        user=current_user,
        fields={
            "client_type": payload.client_type,
            "device_id": payload.device_id,
            "session_id": payload.session_id,
            "user_agent": payload.user_agent,
            "platform": payload.platform,
            "os_version": payload.os_version,
            "app_version": payload.app_version,
            "build_id": payload.build_id,
            "network_type": payload.network_type,
            "event_name": payload.event_name,
            "page_path": payload.page_path,
            "entry_source": payload.entry_source,
        },
        detection_source=DetectionSource.API_RUNTIME,
        request_path=request.url.path,
    )
    client_type = payload.client_type.strip()
    event_name = payload.event_name.strip()
    device_id = _normalize_text(payload.device_id.strip(), max_length=64).lower()
    session_id = _normalize_text(payload.session_id.strip(), max_length=64)
    page_path = _normalize_text(payload.page_path.strip(), max_length=255)
    entry_source = _normalize_text(payload.entry_source.strip(), max_length=64)
    network_type = _normalize_text(payload.network_type.strip(), max_length=32)
    if (
        client_type != CLIENT_TYPE_MP_WEIXIN
        or event_name not in RUNTIME_EVENT_NAME_WHITELIST
        or not _is_uuid(device_id)
        or not _is_valid_runtime_session_id(session_id)
        or not _is_valid_runtime_page_path(page_path)
        or not _is_valid_runtime_entry_source(entry_source)
    ):
        return RuntimeObservationResponse(accepted=False, event_id=0)

    client_ip = _safe_client_ip(request)
    if _is_runtime_rate_limited(
        client_ip=client_ip,
        device_id=device_id,
        session_id=session_id,
    ):
        return RuntimeObservationResponse(accepted=False, event_id=0)
    if await _is_security_rate_limited(
        db=db,
        group="runtime_observation",
        identifiers=_build_runtime_limit_keys(
            client_ip=client_ip,
            device_id=device_id,
            session_id=session_id,
        ),
    ):
        return RuntimeObservationResponse(accepted=False, event_id=0)

    occurred_at = datetime.fromtimestamp(payload.occurred_at_ms / 1000, tz=UTC)
    day_bucket_start = occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_bucket_end = day_bucket_start + timedelta(days=1)
    tick_bucket_start = occurred_at.replace(second=(occurred_at.second // 30) * 30, microsecond=0)
    tick_bucket_end = tick_bucket_start + timedelta(seconds=30)
    dedup_window_start = occurred_at - timedelta(seconds=2)

    sanitized_payload = _sanitize_event_payload(payload.event_payload)
    payload_digest = _stable_payload_digest(sanitized_payload)
    feature_hits = _normalize_feature_hits(payload.matched_features)

    build_time = _normalize_optional_time_string(payload.build_time)
    scope_snapshot = 1 if payload.segment_type == 1 else 0
    user_id = int(current_user.id) if current_user is not None else None

    try:
        recent_dedup_result = await db.execute(
            text(
                """
                SELECT id
                FROM client_runtime_observations
                WHERE device_id = :device_id
                  AND event_name = :event_name
                  AND page_path = :page_path
                  AND entry_source = :entry_source
                  AND event_payload_digest = :event_payload_digest
                  AND occurred_at >= :dedup_window_start
                ORDER BY occurred_at DESC
                LIMIT 1
                """
            ),
            {
                "device_id": device_id,
                "event_name": event_name,
                "page_path": page_path,
                "entry_source": entry_source,
                "event_payload_digest": payload_digest,
                "dedup_window_start": dedup_window_start,
            },
        )
        if recent_dedup_result.scalar_one_or_none() is not None:
            return RuntimeObservationResponse(accepted=False, event_id=0)

        if event_name == "runtime_session_tick":
            tick_dedup_result = await db.execute(
                text(
                    """
                    SELECT id
                    FROM client_runtime_observations
                    WHERE client_type = :client_type
                      AND device_id = :device_id
                      AND session_id = :session_id
                      AND event_name = :event_name
                      AND page_path = :page_path
                      AND entry_source = :entry_source
                      AND scope_snapshot = :scope_snapshot
                      AND network_type = :network_type
                      AND occurred_at >= :tick_bucket_start
                      AND occurred_at < :tick_bucket_end
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "client_type": client_type,
                    "device_id": device_id,
                    "session_id": session_id,
                    "event_name": event_name,
                    "page_path": page_path,
                    "entry_source": entry_source,
                    "scope_snapshot": scope_snapshot,
                    "network_type": network_type,
                    "tick_bucket_start": tick_bucket_start,
                    "tick_bucket_end": tick_bucket_end,
                },
            )
            if tick_dedup_result.scalar_one_or_none() is not None:
                return RuntimeObservationResponse(accepted=False, event_id=0)
        else:
            day_dedup_result = await db.execute(
                text(
                    """
                    SELECT id
                    FROM client_runtime_observations
                    WHERE client_type = :client_type
                      AND device_id = :device_id
                      AND session_id = :session_id
                      AND event_name = :event_name
                      AND page_path = :page_path
                      AND entry_source = :entry_source
                      AND scope_snapshot = :scope_snapshot
                      AND network_type = :network_type
                      AND occurred_at >= :day_bucket_start
                      AND occurred_at < :day_bucket_end
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "client_type": client_type,
                    "device_id": device_id,
                    "session_id": session_id,
                    "event_name": event_name,
                    "page_path": page_path,
                    "entry_source": entry_source,
                    "scope_snapshot": scope_snapshot,
                    "network_type": network_type,
                    "day_bucket_start": day_bucket_start,
                    "day_bucket_end": day_bucket_end,
                },
            )
            if day_dedup_result.scalar_one_or_none() is not None:
                return RuntimeObservationResponse(accepted=False, event_id=0)

        event_id = generate_snowflake_id()
        await db.execute(
            text(
                """
                INSERT INTO client_runtime_observations (
                    id,
                    client_type,
                    client_ip,
                    device_id,
                    session_id,
                    user_id,
                    user_agent,
                    platform,
                    os_version,
                    app_version,
                    build_id,
                    build_time,
                    network_type,
                    scope_snapshot,
                    feature_hits,
                    ua_fetch_status,
                    event_name,
                    page_path,
                    entry_source,
                    event_payload,
                    event_payload_digest,
                    request_id,
                    occurred_at
                ) VALUES (
                    :id,
                    :client_type,
                    :client_ip,
                    :device_id,
                    :session_id,
                    :user_id,
                    :user_agent,
                    :platform,
                    :os_version,
                    :app_version,
                    :build_id,
                    :build_time,
                    :network_type,
                    :scope_snapshot,
                    CAST(:feature_hits AS JSONB),
                    :ua_fetch_status,
                    :event_name,
                    :page_path,
                    :entry_source,
                    CAST(:event_payload AS JSONB),
                    :event_payload_digest,
                    :request_id,
                    :occurred_at
                )
                """
            ),
            {
                "id": event_id,
                "client_type": client_type,
                "client_ip": _normalize_text(client_ip, max_length=45),
                "device_id": device_id,
                "session_id": session_id,
                "user_id": user_id,
                "user_agent": _normalize_text(payload.user_agent.strip(), max_length=2048),
                "platform": _normalize_text(payload.platform.strip(), max_length=32),
                "os_version": _normalize_text(payload.os_version.strip(), max_length=64),
                "app_version": _normalize_text(payload.app_version.strip(), max_length=32),
                "build_id": _normalize_text(payload.build_id.strip(), max_length=64),
                "build_time": build_time,
                "network_type": network_type,
                "scope_snapshot": scope_snapshot,
                "feature_hits": json.dumps(feature_hits, ensure_ascii=False),
                "ua_fetch_status": payload.ua_fetch_status,
                "event_name": event_name,
                "page_path": page_path,
                "entry_source": entry_source,
                "event_payload": json.dumps(sanitized_payload, ensure_ascii=False),
                "event_payload_digest": payload_digest,
                "request_id": _normalize_text(payload.request_id.strip(), max_length=128),
                "occurred_at": occurred_at,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.error("runtime_observation_insert_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="系统错误") from exc

    return RuntimeObservationResponse(accepted=True, event_id=event_id)
