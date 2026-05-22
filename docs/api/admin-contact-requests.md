# 管理端联系人请求接口

## 接口列表

- [未完成请求概览](#未完成请求概览) - `GET /admin-api/contact-requests/incomplete/overview`
- [未完成请求列表](#未完成请求列表) - `GET /admin-api/contact-requests/incomplete`
- [重试 AI 类型搜索](#重试-ai-类型搜索) - `GET /admin-api/contact-requests/ai-types/search`
- [重试模板搜索](#重试模板搜索) - `GET /admin-api/contact-requests/templates/search`
- [重试预检](#重试预检) - `POST /admin-api/contact-requests/{request_id}/retry-precheck`
- [执行重试](#执行重试) - `POST /admin-api/contact-requests/{request_id}/retry`

## 相关文档

- `docs/spec/contact/request-flow.md`
- `docs/api/contact-requests.md`

---

## 未完成请求概览

### 基本信息

- **路径**: `GET /admin-api/contact-requests/incomplete/overview`
- **认证**: Admin Session（必需）
- **说明**: 返回“未完成请求”面板概览数据。

### 请求参数

- 无。

### 成功响应（200）

```json
{
  "incomplete_total": 128,
  "last24h_success_requests": 42,
  "last24h_failed_requests": 17,
  "last24h_failed_attempts": 64,
  "last24h_blocked_attempts": 9
}
```

### 响应字段说明

- `incomplete_total` (integer) - 当前未完成请求总数。
- `last24h_success_requests` (integer) - 近 24 小时重试成功请求数（按 `request_id` 去重）。
- `last24h_failed_requests` (integer) - 近 24 小时重试失败请求数（按 `request_id` 去重）。
- `last24h_failed_attempts` (integer) - 近 24 小时重试失败次数（按重试尝试事件计数）。
- `last24h_blocked_attempts` (integer) - 近 24 小时重试阻断次数（按 `result_status=REJECTED` 计数，排除业务拒绝码 `AI_CONTACT_LIMIT_REACHED` 与 `RETRY_REJECTED`）。

---

## 未完成请求列表

### 基本信息

- **路径**: `GET /admin-api/contact-requests/incomplete`
- **认证**: Admin Session（必需）
- **说明**: 返回“未完成请求”页面列表数据，支持筛选与分页。

### 请求参数

- `ai_type_id` (string, 可选) - 按请求目标 AI 类型过滤。
- `failure_code` (string, 可选) - 按失败代码过滤。
- `status` (integer, 可选) - 按状态过滤。
- `updated_from` (string, 可选) - `updated_at` 起始时间（ISO 8601, UTC）。
- `updated_to` (string, 可选) - `updated_at` 结束时间（ISO 8601, UTC）。
- `limit` (integer, 可选) - 每页条数，范围 `1-100`，默认 `20`。
- `offset` (integer, 可选) - 偏移量，默认 `0`。

### 行为约束

- 默认返回三类请求：
  - `status=PENDING`
  - `status=PROCESSING`
  - `status=FAILED`
- 不返回：
  - `status=ACCEPTED`
  - `status=IGNORED`

### 成功响应（200）

```json
{
  "items": [
    {
      "request_id": "273338979288485888",
      "status": 1,
      "from_qiao_id": "qiao_user_001",
      "to_qiao_id": "qiao_ai_target_001",
      "from_id": "273338979288485111",
      "to_id": null,
      "from_type": 1,
      "to_type": 2,
      "failure_code": "ALL_TEMPLATES_ALREADY_USED",
      "failure_reason_label": "当前用户已用尽该类型可选模板",
      "ai_type_id": "3",
      "ai_type_display_name": "校园学姐",
      "retry_count": 2,
      "is_retryable": true,
      "created_at": "2026-05-22T04:15:01.213000+00:00",
      "expires_at": "2026-05-29T04:15:01.213000+00:00",
      "is_expired": false,
      "updated_at": "2026-05-22T05:01:11.913000+00:00",
      "last_retry_at": "2026-05-22T04:58:11.101000+00:00"
    }
  ],
  "total": 128,
  "limit": 20,
  "offset": 0
}
```

### 响应字段说明

- `request_id` (string) - 请求 ID（Snowflake），使用字符串传输。
- `from_id` / `to_id` (string | null) - 内部 ID，使用字符串传输。
- `from_type` / `to_type` (integer) - 参与方类型，用于前端判断用户跳转行为。
- `failure_code` (string | null) - 失败代码，用于筛选项聚合。
- `failure_reason_label` (string) - 失败原因可读文案。
- `is_expired` (boolean) - 由服务端计算的到期状态（`expires_at <= 当前UTC时间`）。
- 时间字段（`created_at/expires_at/updated_at/last_retry_at`）均为 UTC ISO 8601 字符串。
- 前端展示约定：`created_at` 与 `expires_at` 在未完成请求面板以相对时间显示（例如 `1天23小时前`）；`is_expired=false` 显示“有效”图标，`is_expired=true` 显示“无效”图标。

---

## 重试 AI 类型搜索

### 基本信息

- **路径**: `GET /admin-api/contact-requests/ai-types/search`
- **认证**: Admin Session（必需）
- **说明**: 返回手动重试弹窗可选 AI 类型列表。

### 请求参数

- `q` (string, 可选) - AI 类型 ID 或名称关键字。
- `limit` (integer, 可选) - 每页条数，范围 `1-50`，默认 `20`。
- `page` (integer, 可选) - 页码，范围 `1-200`，默认 `1`。

### 成功响应（200）

```json
{
  "items": [
    {
      "id": "3",
      "text": "[3] 校园学姐",
      "meta": {
        "ai_type_id": "3",
        "ai_type_display_name": "校园学姐",
        "description": "校园聊天与学习规划"
      }
    }
  ],
  "has_more": false
}
```

---

## 重试模板搜索

### 基本信息

- **路径**: `GET /admin-api/contact-requests/templates/search`
- **认证**: Admin Session（必需）
- **说明**: 返回手动重试弹窗可选模板列表。

### 请求参数

- `q` (string, 可选) - 模板 ID 或名称关键字。
- `ai_type_id` (string, 可选) - 模板类型过滤。
- `limit` (integer, 可选) - 每页条数，范围 `1-50`，默认 `20`。
- `page` (integer, 可选) - 页码，范围 `1-200`，默认 `1`。

### 行为约束

- 当 `q` 为空且 `ai_type_id` 为空时，返回空列表。
- 手动重试弹窗默认传入 `ai_type_id` 后返回该类型模板。

### 成功响应（200）

```json
{
  "items": [
    {
      "id": "12",
      "text": "[12] Friendly Default Config (ACTIVE, P=1)",
      "meta": {
        "template_id": "12",
        "display_name": "Friendly Default Config",
        "type_id": "3",
        "type_display_name": "校园学姐",
        "status": "ACTIVE",
        "is_reusable": false,
        "priority": 1,
        "style_id": "7",
        "style_display_name": "温柔风格",
        "personality_id": "3",
        "personality_display_name": "学姐人格",
        "timezone": "Asia/Shanghai",
        "updated_at": "2026-05-22T06:01:11.913000+00:00"
      }
    }
  ],
  "has_more": false
}
```

---

## 重试预检

### 基本信息

- **路径**: `POST /admin-api/contact-requests/{request_id}/retry-precheck`
- **认证**: Admin Session（必需）
- **说明**: 返回指定请求在当前时刻的重试可行性检查结果。

### 路径参数

- `request_id` (string, 必填) - Snowflake 数字字符串。

### 请求参数

```json
{
  "mode": "MANUAL",
  "selected_ai_type_id": "3",
  "selected_template_id": "12"
}
```

### 请求字段说明

- `mode` (enum string, 必填) - 重试模式枚举 `ContactRequestRetryMode`，允许值：`AUTO`、`MANUAL`。
- `selected_ai_type_id` (string, 条件必填) - `mode=MANUAL` 且未传 `selected_template_id` 时必填。
- `selected_template_id` (string, 条件可选) - `mode=MANUAL` 时可选。

### 成功响应（200）

```json
{
  "request_id": "273338979288485888",
  "mode": "MANUAL",
  "requested_ai_type_id": "3",
  "requested_ai_type_name": "校园学姐",
  "availability": {
    "active_template_count": 6,
    "selectable_template_count": 2
  },
  "blocking_errors": [
    {
      "code": "TEMPLATE_ALREADY_USED_BY_USER",
      "level": "BLOCKING",
      "message": "Template has already been used by this user"
    }
  ],
  "warnings": [
    {
      "code": "TEMPLATE_TYPE_MISMATCH",
      "level": "HIGH",
      "message": "Template type does not match selected AI type"
    },
    {
      "code": "TEMPLATE_STATUS_NON_ACTIVE",
      "level": "HIGH",
      "message": "Template status is INACTIVE"
    }
  ],
  "summary": {
    "blocking_count": 1,
    "warning_count": 2,
    "high_risk_count": 2,
    "can_execute": false
  }
}
```

### 行为约束

- 预检结果仅作为即时参考，不保证确认执行时仍然成立。
- 预检返回阻断项时，前端应禁用执行提交。

---

## 执行重试

### 基本信息

- **路径**: `POST /admin-api/contact-requests/{request_id}/retry`
- **认证**: Admin Session（必需）
- **说明**: 执行自动重试或指定模板重试。

### 路径参数

- `request_id` (string, 必填) - Snowflake 数字字符串。

### 请求参数

```json
{
  "mode": "MANUAL",
  "selected_ai_type_id": "3",
  "selected_template_id": "12",
  "force_continue": true,
  "idempotency_key": "retry-273338979288485888-20260523-001",
  "precheck_payload": {
    "checks": [],
    "blocking_errors": [],
    "warnings": [],
    "summary": {
      "blocking_count": 0,
      "warning_count": 0,
      "high_risk_count": 0,
      "can_execute": true
    }
  },
  "alias": "学姐",
  "tags": ["学习", "规划"]
}
```

### 请求字段说明

- `mode` (enum string, 必填) - 重试模式枚举 `ContactRequestRetryMode`，允许值：`AUTO`、`MANUAL`。
- `selected_ai_type_id` (string, 条件必填) - `mode=MANUAL` 且未传 `selected_template_id` 时必填。
- `selected_template_id` (string, 条件可选) - `mode=MANUAL` 时可选。
- `force_continue` (boolean, 必填) - 是否确认继续执行告警重试。
- `idempotency_key` (string, 必填) - 幂等键。
- `precheck_payload` (object, 可选) - 弹窗预检结果快照，执行时用于审计记录。
- `alias` (string, 可选) - 覆盖重试成功后的联系人备注。
- `tags` (array[string], 可选) - 覆盖重试成功后的联系人标签。

### 权限约束

- `mode=AUTO`：已登录管理账号可执行。
- `mode=MANUAL`：仅 `SUPER_ADMIN` 可执行。
- `mode=MANUAL` 且命中告警项时：执行请求要求 `force_continue=true`。

### 成功响应（200）

```json
{
  "attempt_id": "273339000000000001",
  "request_id": "273338979288485888",
  "result_status": "FAILED",
  "result_failure_code": "ALL_TEMPLATES_ALREADY_USED",
  "result_failure_detail": {
    "ai_type_id": 3,
    "type_id": 3,
    "request_id": 273338979288485888
  },
  "request_status_after": 1,
  "retry_count_after": 5,
  "last_retry_at": "2026-05-23T14:22:31.101000+00:00",
  "is_idempotent_replay": false
}
```

### 行为约束

- 重试模式、请求状态、重试结果、规则码使用枚举或命名常量管理，不使用魔法数字与魔法字符串。
- 允许重试的目标请求状态：`PENDING`、`FAILED`。
- `status=PROCESSING` 的请求视为正在处理，执行阶段返回 `409 Conflict`。
- 执行前更新 `retry_count` 与 `last_retry_at`。
- 重试主链路复用统一联系人创建流程。
- `mode=MANUAL` 且仅传 `selected_ai_type_id` 时：按该类型自动选模板并执行，模板仍可能不可用导致失败。
- `mode=MANUAL` 且同时传 `selected_ai_type_id + selected_template_id` 时：使用指定模板执行。
- `mode=MANUAL` 且模板状态非 `ACTIVE`、模板类型与所选类型不一致时：允许执行并记录告警，执行请求需 `force_continue=true`。
- `mode=MANUAL` 且模板已被该用户使用过时：执行阶段强制拦截并返回 `409`。
- 指定模板重试会记录请求类型与模板类型双维度归属：
  - `requested_ai_type_id`
  - `selected_template_type_id`
- 接口返回本次重试执行结果；若命中同 `idempotency_key`，返回历史同键执行结果并标记 `is_idempotent_replay=true`。

### 错误响应

- `400 Bad Request`
  - 请求参数无效
- `403 Forbidden`
  - 权限不足
- `404 Not Found`
  - 请求不存在或模板不存在
- `409 Conflict`
  - 命中阻断规则（例如 `TEMPLATE_ALREADY_USED_BY_USER`）
