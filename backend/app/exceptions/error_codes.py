"""Error code registry and helpers for API error responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import status


@dataclass(frozen=True, slots=True)
class ServiceModuleCode:
    """Registered service/module code pair."""

    service: int
    module: int
    name: str


# SS/MM registration (SSMMEEEE)
SERVICE_MODULE_REGISTRY: tuple[tuple[str, ServiceModuleCode], ...] = (
    ("/api/v1/auth", ServiceModuleCode(service=11, module=1, name="auth")),
    (
        "/api/v1/user/email/send-code",
        ServiceModuleCode(service=12, module=1, name="account_security"),
    ),
    (
        "/api/v1/user/email",
        ServiceModuleCode(service=12, module=1, name="account_security"),
    ),
    (
        "/api/v1/user/phone",
        ServiceModuleCode(service=12, module=1, name="account_security"),
    ),
    (
        "/api/v1/user/username/check",
        ServiceModuleCode(service=13, module=1, name="users"),
    ),
    ("/api/v1/user/profile", ServiceModuleCode(service=13, module=1, name="users")),
    ("/api/v1/user/account", ServiceModuleCode(service=13, module=1, name="users")),
    ("/api/v1/user/settings", ServiceModuleCode(service=13, module=1, name="users")),
    (
        "/api/v1/contact-requests",
        ServiceModuleCode(service=21, module=2, name="contact_requests"),
    ),
    ("/api/v1/contacts", ServiceModuleCode(service=21, module=1, name="contacts")),
    ("/api/v1/discovery", ServiceModuleCode(service=22, module=1, name="discovery")),
    ("/api/v1/media", ServiceModuleCode(service=23, module=1, name="media")),
    ("/api/v1/messages", ServiceModuleCode(service=24, module=1, name="messages")),
    ("/api/v1/lc-im", ServiceModuleCode(service=24, module=2, name="message_access")),
    (
        "/api/v1/leancloud",
        ServiceModuleCode(service=24, module=4, name="message_ingress"),
    ),
    (
        "/api/v1/pages",
        ServiceModuleCode(service=26, module=2, name="pages"),
    ),
    ("/api/v1/system", ServiceModuleCode(service=26, module=1, name="system")),
    ("/admin-api", ServiceModuleCode(service=80, module=1, name="admin_api")),
    ("/ws/messages", ServiceModuleCode(service=24, module=3, name="ws_messages")),
)

DEFAULT_SERVICE_MODULE = ServiceModuleCode(service=90, module=1, name="platform")

PROTECTIVE_DENIAL_FLAG = "__protective_denial__"
PROTECTIVE_DENIAL_CAMOUFLAGE_STATUS_KEY = "camouflage_status_code"
PROTECTIVE_DENIAL_CAMOUFLAGE_MESSAGE_KEY = "camouflage_message"
MIN_CLIENT_ERROR_STATUS = 400
MAX_CLIENT_ERROR_STATUS = 499

# Module-local EEEE registry (4 digits).
# The resolver is message-first to decouple error_code from HTTP status.
MESSAGE_TO_EEEE: dict[str, int] = {
    "参数错误": 1001,
    "请求参数错误": 1001,
    "请求格式错误": 1001,
    "手机号格式无效": 1001,
    "手机号不能为空": 1001,
    "用户名格式有误": 1001,
    "邮箱格式不正确": 1001,
    "无效的分类参数": 1001,
    "缺少 X-Client header": 1001,
    "device_id 缺失": 1001,
    "device_id 无效": 1001,
    "msg_id_client 缺失": 1001,
    "conversation_id 缺失": 1001,
    "content 格式错误": 1001,
    "typing_state 无效": 1001,
    "未知消息类型": 1001,
    "prompt_variables must be a dict": 1001,
    "dimensions must be a list": 1001,
    "Each dimension must be a dict": 1001,
    "position_mapping_params must be a dict": 1001,
    "typing_speed_wpm must be an integer": 1001,
    "typing_speed_wpm must be greater than 0": 1001,
    "No data to update": 1001,
    "prompt cannot be empty": 1001,
    "schema_config is required": 1001,
    "dimensions are required": 1001,
    "initial_position is required for each dimension": 1001,
    "name is required for new dimensions": 1001,
    "Invalid start/end position for mapping": 1001,
    "position_mapping_config must be a dict": 1001,
    "Invalid llm_request_id": 1001,
    "验证码有误，请重新输入": 1002,
    "验证码错误，请重新输入": 1002,
    "验证码已失效，请重新获取": 1003,
    "验证码已过期，请重新获取": 1003,
    "账号或密码错误": 1005,
    "账号已被禁用": 1006,
    "请30秒后再试": 7001,
    "请求过于频繁": 7001,
    "请求过于频繁，请稍后再试": 7001,
    "上传过于频繁，请稍后再试": 7001,
    "今日上传次数已达上限": 7001,
    "今日上传大小已达上限": 7001,
    "需要完成人机验证后再试": 1004,
    "验证失败，请重试": 1004,
    "登录失效": 2001,
    "登录已失效，请重新登录": 2001,
    "认证失效，请重新登录": 2001,
    "需要先登录": 2001,
    "Authentication required": 2001,
    "登录失败": 2002,
    "登录失败，请稍后再试": 2002,
    "登录遇到问题，请联系客服": 2002,
    "发送失败": 2002,
    "无权操作": 2003,
    "无权操作此请求": 2003,
    "客户端未授权": 2003,
    "客户端ID与当前用户不匹配": 2003,
    "操作异常": 4001,
    "请求不存在": 4001,
    "用户不存在": 4001,
    "目标用户不存在": 4001,
    "文件不存在": 4001,
    "Template not found": 4001,
    "Memory not found": 4001,
    "Personality not found": 4001,
    "Style not found": 4001,
    "Entry not found": 4001,
    "Instance not found": 4001,
    "Instance snapshot target not found": 4001,
    "Not found": 4001,
    "已添加该联系人": 4002,
    "联系人数量已达上限": 7002,
    "该用户名已被使用": 4002,
    "该手机号已注册": 4002,
    "该手机号已被使用": 4002,
    "该邮箱已被使用": 4002,
    "dimension name already exists": 4002,
    "已绑定邮箱，请先解绑": 4003,
    "此微信已关联其他账号": 4003,
    "头像文件未激活": 4003,
    "请先绑定手机号": 1008,
    "请先绑定邮箱": 1008,
    "未绑定邮箱": 1008,
    "不支持的验证类型": 1010,
    "当前仅支持头像上传": 1010,
    "不支持的文件格式": 1010,
    "仅支持中国大陆手机号": 1010,
    "Invalid algorithm": 1010,
}

MESSAGE_FRAGMENT_TO_EEEE: tuple[tuple[str, int], ...] = (
    ("验证码有误", 1002),
    ("验证码错误", 1002),
    ("验证码已失效", 1003),
    ("验证码已过期", 1003),
    ("人机验证", 1004),
    ("验证失败", 1004),
    ("账号或密码错误", 1005),
    ("账号已被禁用", 1006),
    ("请求过于频繁", 7001),
    ("上传过于频繁", 7001),
    ("已达上限", 7002),
    ("登录失效", 2001),
    ("认证失效", 2001),
    ("登录失败", 2002),
    ("无权", 2003),
    ("未授权", 2003),
    ("不存在", 4001),
    ("操作异常", 4001),
    ("已被使用", 4002),
    ("已注册", 4002),
    ("已关联", 4003),
    ("已绑定", 4003),
    ("请先绑定", 1008),
    ("不支持", 1010),
    ("参数错误", 1001),
    ("格式无效", 1001),
    ("not found", 4001),
    ("must be a dict", 1001),
    ("must be a list", 1001),
    ("must be an integer", 1001),
    ("must be greater than 0", 1001),
    ("is required", 1001),
    ("cannot be empty", 1001),
    ("No data to update", 1001),
    ("Invalid llm_request_id", 1001),
)

STATUS_TO_FALLBACK_EEEE: dict[int, int] = {
    status.HTTP_400_BAD_REQUEST: 1001,
    status.HTTP_401_UNAUTHORIZED: 2001,
    status.HTTP_403_FORBIDDEN: 2003,
    status.HTTP_404_NOT_FOUND: 4001,
    status.HTTP_409_CONFLICT: 4002,
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: 1001,
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: 1010,
    status.HTTP_422_UNPROCESSABLE_ENTITY: 1001,
    status.HTTP_428_PRECONDITION_REQUIRED: 1001,
    status.HTTP_429_TOO_MANY_REQUESTS: 7001,
}

STATUS_TO_SYSTEM_EEEE: dict[int, int] = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: 9001,
    status.HTTP_501_NOT_IMPLEMENTED: 9002,
    status.HTTP_502_BAD_GATEWAY: 9003,
    status.HTTP_503_SERVICE_UNAVAILABLE: 9004,
    status.HTTP_504_GATEWAY_TIMEOUT: 9005,
}


def resolve_service_module(path: str) -> ServiceModuleCode:
    """Resolve registered service/module from request path."""
    for prefix, code in SERVICE_MODULE_REGISTRY:
        if path.startswith(prefix):
            return code
    return DEFAULT_SERVICE_MODULE


def _normalize_message(message: str) -> str:
    return message.strip()


def _extract_message(detail: object | None) -> str | None:
    if isinstance(detail, str):
        normalized = _normalize_message(detail)
        return normalized if normalized else None
    if isinstance(detail, Mapping):
        value = detail.get("message")
        if isinstance(value, str):
            normalized = _normalize_message(value)
            return normalized if normalized else None
    return None


def resolve_error_eeee(status_code: int, detail: object | None = None) -> int:
    """Resolve module-local EEEE code from explicit rules."""
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return STATUS_TO_SYSTEM_EEEE.get(status_code, 9999)

    message = _extract_message(detail)
    if message:
        explicit = MESSAGE_TO_EEEE.get(message)
        if explicit is not None:
            return explicit
        for fragment, eeee in MESSAGE_FRAGMENT_TO_EEEE:
            if fragment in message:
                return eeee

    return STATUS_TO_FALLBACK_EEEE.get(status_code, 1999)


def build_error_code(path: str, status_code: int, detail: object | None = None) -> int:
    """Build SSMMEEEE numeric code."""
    sm = resolve_service_module(path)
    eeee = resolve_error_eeee(status_code=status_code, detail=detail)
    return int(f"{sm.service:02d}{sm.module:02d}{eeee:04d}")


def build_protective_denial_detail(
    *,
    reason: str,
    camouflage_status_code: int = status.HTTP_400_BAD_REQUEST,
    camouflage_message: str = "操作异常",
    risk_rule_id: str | None = None,
    internal_risk_code: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build detail payload for protective denial logs without exposing response internals."""
    detail: dict[str, object] = {
        PROTECTIVE_DENIAL_FLAG: True,
        "risk_reason": reason,
        PROTECTIVE_DENIAL_CAMOUFLAGE_STATUS_KEY: camouflage_status_code,
        PROTECTIVE_DENIAL_CAMOUFLAGE_MESSAGE_KEY: camouflage_message,
    }
    if risk_rule_id:
        detail["risk_rule_id"] = risk_rule_id
    if internal_risk_code:
        detail["internal_risk_code"] = internal_risk_code
    if metadata:
        detail.update(metadata)
    return detail


def is_protective_denial_detail(detail: object | None) -> bool:
    """Return whether the detail payload marks a protective denial event."""
    return isinstance(detail, Mapping) and detail.get(PROTECTIVE_DENIAL_FLAG) is True


def resolve_protective_denial_response(detail: object | None) -> tuple[int, str]:
    """Resolve the externally returned tuple for protective denial events."""
    if not isinstance(detail, Mapping):
        return status.HTTP_400_BAD_REQUEST, "操作异常"

    raw_status = detail.get(PROTECTIVE_DENIAL_CAMOUFLAGE_STATUS_KEY)
    status_code = (
        raw_status
        if isinstance(raw_status, int)
        and MIN_CLIENT_ERROR_STATUS <= raw_status <= MAX_CLIENT_ERROR_STATUS
        else status.HTTP_400_BAD_REQUEST
    )

    raw_message = detail.get(PROTECTIVE_DENIAL_CAMOUFLAGE_MESSAGE_KEY)
    if isinstance(raw_message, str):
        normalized = _normalize_message(raw_message)
        if normalized:
            return status_code, normalized

    return status_code, "操作异常"
