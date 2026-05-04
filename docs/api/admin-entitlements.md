# 管理端权益操作接口

## 接口列表

- [搜索权益操作目标用户](#搜索权益操作目标用户) - `GET /admin-api/entitlements/users/search`
- [查询用户全部权益资产](#查询用户全部权益资产) - `GET /admin-api/entitlements/users/assets`
- [查询权益账户快照](#查询权益账户快照) - `GET /admin-api/entitlements/account-snapshot`
- [管理员发放/调整权益](#管理员发放调整权益) - `POST /admin-api/entitlements/operations`

## 相关文档

- `docs/plans/2026-04-15-entitlement-ledger-refactor.md`
- `docs/api/contacts.md`
- `docs/api/invitations.md`

---

## 搜索权益操作目标用户

### 基本信息

- **路径**: `GET /admin-api/entitlements/users/search`
- **认证**: Admin Session（必需）
- **说明**: 为权益操作台用户选择器提供搜索结果，返回脱敏手机号与邮箱。

### 请求参数

- `q` (string, 可选) - 搜索关键词，支持用户 ID、用户名、手机号、邮箱。
- `limit` (integer, 可选) - 最大返回条数，范围 `1-50`，默认 `20`。
- `page` (integer, 可选) - 页码，从 `1` 开始，默认 `1`。

### 成功响应（200）

```json
{
  "items": [
    {
      "id": "10001",
      "text": "[10001] | alice | +86 138******00 | a***@example.com",
      "meta": {
        "user_id": "10001",
        "username": "alice",
        "phone": "+86 138******00",
        "email": "a***@example.com"
      }
    }
  ],
  "has_more": false
}
```

### 响应字段说明

- `items` (array) - 匹配用户列表。
- `items[].id` (string) - 用户 ID 字符串，前端应按字符串传回写接口，避免大整数精度丢失。
- `items[].text` (string) - 下拉展示文案，包含用户 ID、用户名、脱敏手机号、脱敏邮箱（缺失字段不显示）。
- `items[].meta` (object) - 附加信息，包含 `user_id/username/phone/email`。
- `has_more` (boolean) - 是否存在下一页搜索结果。
- 当 `q` 为空时，返回空数组。

---

## 查询用户全部权益资产

### 基本信息

- **路径**: `GET /admin-api/entitlements/users/assets`
- **认证**: Admin Session（必需）
- **说明**: 返回指定用户在所有激活权益类型下的资产数量，用于管理端“查找用户”区域展示。

### 请求参数

- `user_id` (integer, 必填) - 目标用户 ID，必须大于 0。

### 成功响应（200）

```json
{
  "user_id": 10001,
  "items": [
    {
      "entitlement_type_code": "ai_contact_limit",
      "account_exists": true,
      "granted_total": 5,
      "used_total": 1,
      "available_total": 4,
      "version": 3
    }
  ]
}
```

### 响应字段说明

- `items` (array) - 当前所有激活权益类型对应的资产快照。
- `account_exists=false` 表示该权益类型尚未为此用户创建账户，数量字段均返回 `0`。

### 错误响应

- `404 Not Found`
  - 用户不存在

---

## 查询权益账户快照

### 基本信息

- **路径**: `GET /admin-api/entitlements/account-snapshot`
- **认证**: Admin Session（必需）
- **说明**: 为权益操作台提供“当前数量/预计操作后数量”计算的基础快照。

### 请求参数

- `user_id` (integer, 必填) - 目标用户 ID，必须大于 0。
- `entitlement_type_code` (string, 必填) - 权益类型编码。

### 成功响应（200）

```json
{
  "user_id": 10001,
  "entitlement_type_code": "ai_contact_limit",
  "account_exists": true,
  "granted_total": 5,
  "used_total": 1,
  "available_total": 4,
  "version": 3
}
```

### 错误响应

- `400 Bad Request`
  - 权益类型参数无效
  - 权益类型不存在或未启用
- `404 Not Found`
  - 用户不存在

---

## 管理员发放/调整权益

### 基本信息

- **路径**: `POST /admin-api/entitlements/operations`
- **认证**: Admin Session（必需）
- **说明**: 统一通过 service 写入 `user_entitlement_ledger` 并更新 `user_entitlement_accounts`，禁止直接改表。

### 请求参数

```json
{
  "user_id": "10001",
  "entitlement_type_code": "ai_contact_limit",
  "operation_type": "grant",
  "delta": 2,
  "reason_code": "admin_activity_reward",
  "idempotency_key": "ops_20260416_user10001_reward1",
  "remark": "活动补发"
}
```

### 字段说明

- `user_id` (string, 必填) - 目标用户 ID 字符串，必须是大于 0 的纯数字字符串（避免前端大整数精度丢失）。
- `entitlement_type_code` (string, 必填) - 权益类型编码（如 `ai_contact_limit`）。
- `operation_type` (string, 必填) - 操作类型：
  - `grant`: 发放（`delta` 必须 > 0）
  - `adjust`: 调整（`delta` 可正可负，但不能为 0）
- `delta` (integer, 必填) - 对 `granted_total` 的增量。
- `reason_code` (string, 必填) - 原因码，必须在 `entitlement_reason_codes` 中且为激活状态，并且其 `applies_to` 必须匹配当前 `operation_type`（`grant`/`adjust`/`both`）。
- `idempotency_key` (string, 必填) - 幂等键，建议由管理端页面按一次业务动作唯一生成。
- `remark` (string, 可选) - 操作备注，留空时不写入备注信息。

### 成功响应（200）

```json
{
  "accepted": true,
  "applied": true,
  "user_id": 10001,
  "entitlement_type_code": "ai_contact_limit",
  "action_type": 1,
  "delta_granted": 2,
  "delta_used": 0,
  "source_type": "admin_manual_grant",
  "reason_code": "admin_activity_reward",
  "idempotency_key": "ops_20260416_user10001_reward1",
  "granted_total": 5,
  "used_total": 0,
  "available_total": 5,
  "version": 3
}
```

### 响应字段说明

- `applied=false` 表示命中幂等，未重复写账本；账户快照仍会返回当前值。
- `action_type` 与账本一致：`1=grant`、`4=adjust`（管理端仅支持这两类）。
- `source_type` 固定由后端枚举与账本约束决定：
  - `admin_manual_grant`
  - `admin_manual_adjust`

### 审计日志语义

- 接口每次调用都会写入 `admin_operation_logs`（包含幂等命中场景）。
- `resource_type` 固定为 `entitlement_operation`。
- `operation_desc` 记录人类可读摘要。
- `operation_meta` 记录结构化字段：`operation_type/user_id/entitlement_type_code/delta/reason_code/applied/idempotency_key`。

### 错误响应

- `400 Bad Request`
  - 参数不合法（如 `grant` 传入 `delta<=0`、`adjust` 传入 `delta=0`）
  - 字典不存在或未启用（`entitlement_type_code` / `reason_code`）
  - 原因码与操作类型不匹配（例如 `grant` 使用了仅 `adjust` 可用的原因码）
  - 调整后余额非法（导致 `granted_total < used_total`）
- `401 Unauthorized`
  - 管理员会话无效
- `403 Forbidden`
  - 管理员无权限执行当前操作（如 `viewer` 角色）
- `500 Internal Server Error`
  - 非预期系统错误
