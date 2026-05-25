# 管理后台安全管理 API

## 接口列表

- `GET /admin-api/security/ip-blocks`
- `POST /admin-api/security/ip-blocks`
- `POST /admin-api/security/ip-blocks/{block_id}/release`

所有接口复用 Starlette-Admin Session 鉴权。

## 角色权限

- `SUPER_ADMIN`、`ADMIN`：可读可写（封禁 / 解封）
- `VIEWER`：只读（仅查询）

## 查询封禁记录

- 路径：`GET /admin-api/security/ip-blocks`
- 查询参数：
  - `status`: `active | released | all`（默认 `active`）
  - `limit`: `1~200`（默认 `100`）

### 成功响应

```json
{
  "items": [
    {
      "id": 123456789,
      "target": "203.0.113.0/24",
      "target_type": "cidr",
      "status": 1,
      "severity_level": 3,
      "reason_code": "manual_block",
      "rule_code": "manual_block",
      "rule_version": "manual_v1",
      "source": "admin_manual",
      "request_path": "/admin-api/security/ip-blocks",
      "request_method": "POST",
      "evidence_payload": {
        "manual_reason": "abuse control",
        "target_type": "cidr",
        "target": "203.0.113.0/24",
        "is_permanent": false,
        "ttl_seconds": 3600
      },
      "hit_count": 1,
      "blocked_at": "2026-05-25T10:00:00+00:00",
      "expires_at": "2026-05-25T11:00:00+00:00",
      "released_at": null,
      "release_reason": null,
      "is_permanent": false
    }
  ]
}
```

## 新增/更新手工封禁

- 路径：`POST /admin-api/security/ip-blocks`

### 请求体

```json
{
  "target": "203.0.113.0/24",
  "severity_level": 3,
  "reason": "abuse control",
  "is_permanent": false,
  "ttl_seconds": 3600
}
```

### 字段约束

- `target`: 非空；服务端自动识别类型：包含 `/` 按 `cidr` 校验，否则按 `single_ip` 校验
- `severity_level`: `1~4`
- `reason`: 非空，最大 500
- `is_permanent=true` 时忽略 `ttl_seconds`
- `is_permanent=false` 时 `ttl_seconds` 必填且 > 0

### 行为

- 命中同一活动记录（同 `target_network`）时执行更新
- 否则创建新记录
- `rule_code/reason_code/source` 固定为手工值，`rule_version=manual_v1`
- 写入 `admin_operation_logs` 审计日志

## 解封

- 路径：`POST /admin-api/security/ip-blocks/{block_id}/release`

### 请求体

```json
{
  "release_reason": "false positive confirmed"
}
```

### 字段约束

- `release_reason` 必填，最大 128
- 仅允许解封当前仍生效的封禁记录（`status=ACTIVE` 且 `expires_at` 晚于当前时间）

### 行为

- 更新为 `status=RELEASED`
- 写入 `released_at`、`release_reason`
- 写入 `admin_operation_logs` 审计日志
