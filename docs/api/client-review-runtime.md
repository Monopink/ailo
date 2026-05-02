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
  "device_id": "d_xxxxx",
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
- `device_id` (string): 设备标识，最大 64
- `user_agent` (string): 运行态 UA，最大 2048
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
- `403`: 网关访问控制拒绝
- `500`: 系统错误

### 判定规则

- 当请求携带有效鉴权且账号内部标记命中受限分段时，返回 `segment_type=1`。
- 当请求未携带有效鉴权且 `system_configs.mp_weixin_review_mode=true` 时，返回 `segment_type=1`。
- 当未命中账号标记时，服务端按运行态特征判定返回 `segment_type`。
- 当运行态判定命中受限分段时，服务端会触发账号内部标记升级（仅 `0 -> 1`）。
- `preflight_probe_result` 作为观测事件名保留，不做语义改名。

## 上报运行态观测事件

### 基本信息

- 路径：`POST /api/v1/client/runtime-observations`
- 认证：无需认证（可携带 Bearer Token）

### 请求体

```json
{
  "client_type": "mp_weixin",
  "device_id": "d_xxxxx",
  "session_id": "s_xxxxx",
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
- `device_id` (string, required): 设备标识，最大 64
- `session_id` (string): 会话标识，最大 64
- `user_agent` (string): 运行态 UA，最大 2048
- `platform` (string): 平台标识，最大 32
- `os_version` (string): 系统版本，最大 64
- `app_version` (string): 客户端版本，最大 32
- `build_id` (string): 构建标识，最大 64
- `build_time` (string | null): 构建时间（ISO8601）
- `network_type` (string): 网络类型，最大 32
- `segment_type` (integer): 分段结果（`0=standard`、`1=limited`）
- `matched_features` (array): 命中特征集合，元素最大 64
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
- 当前白名单事件：`boot_route_decision`、`preflight_probe_result`、`preview_guard_redirect`、`login_clipboard_intake`、`invite_intake_attempt`、`runtime_session_tick`。
- 当 `event_payload.clipboard_raw_text` 存在时，单条最大 2048 字符，超长按 2048 截断后入库。
- 同一 2 秒窗口内，若 `device_id + event_name + page_path + entry_source + event_payload_digest` 一致，仅首条写入。
- 除 `runtime_session_tick` 外：同一自然日（UTC）内，若 `client_type + device_id + session_id + event_name + page_path + entry_source + segment_type + network_type` 完全一致，仅首条会写入，后续返回 `accepted=false`。
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

- `403`: 网关访问控制拒绝
- `500`: 系统错误
