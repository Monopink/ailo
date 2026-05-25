# 客户端运行态观测接口

## 接口列表

- `POST /api/v1/client/preflight-probe`
- `POST /api/v1/client/runtime-observations`

## 运行态分段判定

### 基本信息

- 路径：`POST /api/v1/client/preflight-probe`
- 认证：无需认证（可携带 Bearer Token）
- 用途：统一返回客户端当前分段结果，客户端启动与登录后都调用该接口

### 请求体

```json
{
  "client_type": "mp_weixin",
  "device_id": "6f3d2f8c-0b60-4f05-b145-6c2f6b5bf2d8",
  "user_agent": "Mozilla/5.0 ...",
  "platform": "windows",
  "os_version": "10",
  "app_version": "1.0.0",
  "build_id": "20260501.1",
  "build_time": "2026-05-01T08:00:00Z",
  "occurred_at_ms": 1760000000000
}
```

### 请求字段约束

- `client_type` (string, required): 客户端标识，枚举值：`mp_weixin`
- `device_id` (string): 设备标识，必须为 UUID（v1-v5），最大 64
- `user_agent` (string): 运行态 UA 快照（观测字段），最大 2048
- `platform` (string): 平台标识，最大 32
- `os_version` (string): 系统版本，最大 64
- `app_version` (string): 客户端版本，最大 32
- `build_id` (string): 构建标识，最大 64
- `build_time` (string | null): 构建时间（ISO8601）
- `occurred_at_ms` (integer, required): 事件发生时间 UTC 时间戳（毫秒）

### 成功响应（200）

```json
{
  "segment_type": 1,
  "server_time_ms": 1760000000100
}
```

### 响应字段说明

- `segment_type` (integer): 分段结果（`0=standard`、`1=limited`）
- `server_time_ms` (integer): 服务端 UTC 时间戳（毫秒）

### 错误响应

- `400`: 参数错误
- `403`: 安全拒绝（IP 封禁或攻击签名命中）
- `500`: 系统错误

#### `403` 响应约束

- `reason`: `ATTACK_DETECTED` 或 `IP_BLOCKED`
- `request_id`: 必须返回，供风控日志追踪
- 客户端收到 `403` 时禁止重试同请求体（需等待用户行为变化或封禁过期）
- 客户端收到 `403` 时视为“服务端可达但请求被拒绝”，禁止进入 preview 离线审核页；仅允许提示“服务繁忙，请稍后再试”并走登录/重试链路。
- preview 兜底仅允许在“首次进入小程序”的健康探测决策中评估一次；首次决策结果必须持久化并永久生效。
- preview 时间窗由客户端配置项管理（默认 36 小时）；`build_time` 缺失或非法时必须禁用 preview 兜底。

### 判定规则

- 分段判定业务规则见：`docs/spec/review-mode.md` 的“审核员分段判定”章节。
- `preflight-probe` 判定输入包含 `build_id`、`build_time`、`user_agent`、`client_ip`。
- `preflight_probe_result` 作为观测事件名保留，不做语义改名。

## 上报运行态观测事件

### 基本信息

- 路径：`POST /api/v1/client/runtime-observations`
- 认证：无需认证（可携带 Bearer Token）

### 请求体

```json
{
  "client_type": "mp_weixin",
  "device_id": "6f3d2f8c-0b60-4f05-b145-6c2f6b5bf2d8",
  "session_id": "runtime:boot:20260514",
  "user_agent": "Mozilla/5.0 ...",
  "platform": "windows",
  "os_version": "10",
  "app_version": "1.0.0",
  "build_id": "20260501.1",
  "build_time": "2026-05-01T08:00:00Z",
  "network_type": "wifi",
  "segment_type": 1,
  "matched_features": [
    "xweb",
    "windows_wechat_runtime",
    "mini_program_windows"
  ],
  "ua_fetch_status": 1,
  "event_name": "boot_route_decision",
  "page_path": "/pages/boot/boot",
  "entry_source": "cold_start",
  "event_payload": {
    "route_target": "square_demo",
    "clipboard_raw_text": "敲敲好友都在用，K8P2Q7",
    "clipboard_source": "wx_getClipboardData",
    "clipboard_collected_at_ms": 1760000000001
  },
  "request_id": "",
  "occurred_at_ms": 1760000000000
}
```

### 请求字段约束

- `client_type` (string, required): 客户端标识，枚举值：`mp_weixin`
- `device_id` (string, required): 设备标识，必须为 UUID（v1-v5），最大 64
- `session_id` (string): 会话标识，最大 64
- `user_agent` (string): 运行态 UA 快照（观测字段），最大 2048
- `platform` (string): 平台标识，最大 32
- `os_version` (string): 系统版本，最大 64
- `app_version` (string): 客户端版本，最大 32
- `build_id` (string): 构建标识，最大 64
- `build_time` (string | null): 构建时间（ISO8601）
- `network_type` (string): 网络类型，最大 32
- `segment_type` (integer): 分段结果（`0=standard`、`1=limited`）
- `matched_features` (array): 客户端运行态命中特征快照，元素最大 64
- `ua_fetch_status` (integer): UA 读取状态（`0=unknown`、`1=success`、`2=failed`、`3=unavailable`）
- `event_name` (string, required): 事件名，最大 64
- `page_path` (string): 页面路径，最大 255
- `entry_source` (string): 入口来源，最大 64
- `event_payload` (object): 事件负载 JSON；用于承载剪贴板内容与操作行为等可变结构
- `request_id` (string): 请求标识，最大 128
- `occurred_at_ms` (integer, required): 事件发生时间 UTC 时间戳（毫秒）

### 后端落库映射

- `segment_type` -> `client_runtime_observations.scope_snapshot`
- `ua_fetch_status` -> `client_runtime_observations.ua_fetch_status`
- `matched_features` -> `client_runtime_observations.feature_hits`
- `user_agent` -> `client_runtime_observations.user_agent`
- `entry_source` -> `client_runtime_observations.entry_source`
- `event_payload` -> `client_runtime_observations.event_payload`
- `user_id` 由服务端根据鉴权态写入 `client_runtime_observations.user_id`

### 接收规则

- 该接口允许匿名调用。
- 匿名请求写入 `client_runtime_observations.user_id = null`。
- 携带有效鉴权时，服务端从 token 解析并写入 `client_runtime_observations.user_id`。
- `device_id` 为空时，事件会被忽略并返回 `accepted=false`。
- 仅接收 `client_type=mp_weixin` 且 `event_name` 命中白名单的事件。
- 当前白名单事件：`boot_route_decision`、`preflight_probe_result`、`preview_guard_redirect`、`login_clipboard_intake`、`login_bootstrap_failed`、`login_status_check_failed`、`login_bind_failed`、`login_phone_auth_rejected`、`invite_intake_attempt`、`runtime_session_tick`、`official_account_follow_attempt`、`official_account_follow_fallback_shown`、`message_connect_failed`、`message_connect_recovered`、`message_send_failed`、`ws_auth_failed`、`ws_ack_timeout`。
- 消息服务故障事件（`message_connect_failed`、`message_connect_recovered`、`message_send_failed`、`ws_auth_failed`、`ws_ack_timeout`）使用 `entry_source=message_service`。
- 消息服务故障事件的 `event_payload` 建议字段：`error_code`、`error_message`、`connection_state`、`reconnect_attempt`、`phase`、`conv_id`、`msg_id`、`message_type`、`recovery_mode`、`probe_interval_ms`、`probe_attempt`、`occurred_at_ms`。
- 当小程序出现 `createSocketTask:fail url not in domain list` 时，`error_code` 必须归一为 `WS_DOMAIN_NOT_ALLOWED`，`error_message` 保留原始错误文本用于诊断。
- 当 `event_payload.clipboard_raw_text` 存在时，单条最大 2048 字符，超长按 2048 截断后入库。
- 同一 2 秒窗口内，若 `device_id + event_name + page_path + entry_source + event_payload_digest` 一致，仅首条写入。
- 除 `runtime_session_tick` 与消息服务故障事件外：同一自然日（UTC）内，若 `client_type + device_id + session_id + event_name + page_path + entry_source + segment_type + network_type` 完全一致，仅首条会写入，后续返回 `accepted=false`。
- 消息服务故障事件不参与“同日首条”去重，保留连续故障样本；仍受 2 秒近窗去重与接口限频约束。
- `runtime_session_tick` 使用 30 秒时间桶去重，保留周期性观测样本。
- 服务端对 `ip + device_id + session_id` 执行分层限频（秒级与日级）；超限事件返回 `accepted=false`。
- 客户端离线时可将 `runtime_session_tick` 暂存本地；恢复网络后允许按原始 `occurred_at_ms` 补发。

### 成功响应（202）

```json
{
  "accepted": true,
  "event_id": 1987654321000
}
```

### 忽略响应（202）

```json
{
  "accepted": false,
  "event_id": 0
}
```

### 错误响应

- `403`: 安全拒绝（IP 封禁或攻击签名命中）
- `500`: 系统错误

#### `403` 响应约束

- `reason`: `ATTACK_DETECTED` 或 `IP_BLOCKED`
- `request_id`: 必须返回，供风控日志追踪
- 客户端遇到 `403` 时应停止本轮自动补报，避免触发重复处罚。
- 客户端不得将该场景视为“服务端不可达”；preview 兜底仅用于网络不可达且仍处于构建后 36 小时窗口内。
