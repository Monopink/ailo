# 管理端权益操作接口

## 接口列表

- [管理员发放/调整权益](#管理员发放调整权益) - `POST /admin-api/entitlements/operations`

## 相关文档

- `docs/plans/2026-04-15-entitlement-ledger-refactor.md`
- `docs/api/contacts.md`
- `docs/api/invitations.md`

---

## 管理员发放/调整权益

### 基本信息

- **路径**: `POST /admin-api/entitlements/operations`
- **认证**: Admin Session（必需）
- **说明**: 统一通过 service 写入 `user_entitlement_ledger` 并更新 `user_entitlement_accounts`，禁止直接改表。

### 请求参数

```json
{
  "user_id": 10001,
  "entitlement_type_code": "ai_contact_limit",
  "operation_type": "grant",
  "delta": 2,
  "reason_code": "admin_activity_reward",
  "idempotency_key": "ops_20260416_user10001_reward1",
  "remark": "活动补发"
}
```

### 字段说明

- `user_id` (integer, 必填) - 目标用户 ID，必须大于 0。
- `entitlement_type_code` (string, 必填) - 权益类型编码（如 `ai_contact_limit`）。
- `operation_type` (string, 必填) - 操作类型：
  - `grant`: 发放（`delta` 必须 > 0）
  - `adjust`: 调整（`delta` 可正可负，但不能为 0）
- `delta` (integer, 必填) - 对 `granted_total` 的增量。
- `reason_code` (string, 必填) - 原因码，必须在 `entitlement_reason_codes` 中且为激活状态。
- `idempotency_key` (string, 必填) - 幂等键，建议由管理端页面按一次业务动作唯一生成。
- `remark` (string, 必填) - 操作备注，会进入账本 `event_payload` 和管理操作日志。

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

### 错误响应

- `400 Bad Request`
  - 参数不合法（如 `grant` 传入 `delta<=0`、`adjust` 传入 `delta=0`）
  - 字典不存在或未启用（`entitlement_type_code` / `reason_code`）
  - 调整后余额非法（导致 `granted_total < used_total`）
- `401 Unauthorized`
  - 管理员会话无效
- `403 Forbidden`
  - 管理员无权限执行当前操作（如 `viewer` 角色）
- `500 Internal Server Error`
  - 非预期系统错误
