# Leancloud 接口

LeanCloud 专用的客户端 IM 接口统一放在 `lc-im` 命名空间下，涵盖系统配置、客户端鉴权签名等，所有客户端接口都要求调用方隐藏第三方实现细节，只暴露业务含义。LeanCloud服务端回调使用 `leancloud`命名空间。

## 接口列表

- [获取消息服务配置](#获取消息服务配置) - `GET /api/v1/lc-im/config`
- [获取 LeanCloud 客户端签名](#获取-leancloud-客户端签名) - `POST /api/v1/lc-im/signature`
- [注册或续租 LeanCloud Presence](#注册或续租-leancloud-presence) - `POST /api/v1/lc-im/presence`
- [LeanCloud 消息 Webhook](#leancloud-消息-webhook) - `POST /api/v1/leancloud/webhook/{webhook_token}`

---

## 获取消息服务配置

### 基本信息

- **路径**: `GET /api/v1/lc-im/config`
- **认证**: Bearer Token（必需）
- **说明**: 下发 LeanCloud 系统级配置，前端初始化 IM 客户端前必须调用

### 请求参数

无

### 成功响应 (200)

```json
{
  "im_conv_id": "68edda0a554ecc6e8843b246",
  "signature_algorithm": "HMAC-SHA1",
  "signature_version": "v1",
  "signature_ttl_ms": 3600000
}
```

**字段说明**:

- `im_conv_id` (string) - LeanCloud 系统对话 ID，所有消息都在该对话发送
- `signature_algorithm` (string) - 客户端鉴权所采用的算法
- `signature_version` (string) - 签名协议版本，便于灰度升级
- `signature_ttl_ms` (integer) - 签名有效期（毫秒）

### 错误响应

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- `im_conv_id` 由系统配置中心维护并可随时变更，客户端应在应用启动和重连时主动拉取

---

## 获取 LeanCloud 客户端签名

### 基本信息

- **路径**: `POST /api/v1/lc-im/signature`
- **认证**: Bearer Token（必需）
- **说明**: 返回 LeanCloud 登录所需的签名、时间戳和随机数

### 请求体

```json
{
  "client_id": "qiao_user001"
}
```

**字段说明**:

- `client_id` (string, 必填) - IM 客户端 ID，等同用户的 `qiao_id`

### 成功响应 (200)

```json
{
  "client_id": "qiao_user001",
  "signature": "hmac_sha1_signature",
  "timestamp": 1710001111000,
  "nonce": "random_nonce_string",
  "expires_in": 3600
}
```

**字段说明**:

- `client_id` (string) - 与请求一致
- `signature` (string) - 使用 HMAC-SHA1 生成的签名
- `timestamp` (integer) - 生成签名的时间戳（毫秒）
- `nonce` (string) - 随机字符串，防止重放
- `expires_in` (integer) - 签名有效期（秒），与 `signature_ttl_ms` 一致

### 错误响应

**400 Bad Request**:

- `"参数错误"` - `client_id` 缺失或格式错误

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务器内部错误

### 业务说明

- 签名通过 `HMAC_SHA1(app_secret, client_id + timestamp + nonce)` 生成
- 客户端在连接 LeanCloud SDK 时传入 `client_id`、`signature`、`timestamp`、`nonce`
- 接口会根据 `lc-im/config` 中的版本号返回不同的签名格式，前端不得写死
- 本接口只负责 SDK 登录签名，不负责 `message_endpoints` 注册/续租

---

## 注册或续租 LeanCloud Presence

### 基本信息

- **路径**: `POST /api/v1/lc-im/presence`
- **认证**: Bearer Token（必需）
- **说明**: 注册或续租 LeanCloud USER endpoint，用于 timeline outbox 派发

### 请求体

```json
{
  "client_id": "qiao_user001",
  "client_kind": 2
}
```

**字段说明**:

- `client_id` (string, 必填) - LeanCloud client_id，必须等于当前登录用户 `qiao_id`
- `client_kind` (integer, 可选) - 客户端类型（web/miniprogram/ios/android）

### 成功响应 (200)

```json
{
  "endpoint_id": 223788765171155062,
  "client_id": "qiao_user001",
  "lease_ttl_days": 365,
  "lease_expires_at_ms": 1793808000000
}
```

**字段说明**:

- `endpoint_id` (integer) - `message_endpoints.id`
- `client_id` (string) - 注册的 LeanCloud client_id
- `lease_ttl_days` (integer) - endpoint 租约天数（固定为 365）
- `lease_expires_at_ms` (integer) - 租约到期时间戳（毫秒）

### 错误响应

**400 Bad Request**:

- `"客户端ID与当前用户不匹配"` - 请求体 `client_id` 与登录用户不一致

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误（error_code）"` - 服务端配置或写库失败

### 业务说明

- LeanCloud 使用 USER 粒度 endpoint（`endpoint_scope=USER`，`device_id=NULL`）
- `target_key` 固定为 `client_id`
- 该接口可重复调用，重复调用会续租同一 endpoint（幂等）
- 客户端应在 LeanCloud SDK 建连成功后立即调用，并在会话期间按租约续租

---

## LeanCloud 消息 Webhook

### 基本信息

- **路径**: `POST /api/v1/leancloud/webhook/{webhook_token}`
- **认证**:
  - 路径参数 `webhook_token`（服务端生成）
- **说明**: LeanCloud 推送消息和事件的入口，成功返回 `{ "code": 200 }`

### 路径参数

- `webhook_token` (string, 必填) - 服务端配置的安全令牌

### 请求体（示例）

```json
{
  "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
  "conv": { "objectId": "68edda0a554ecc6e8843b246" },
  "from": "qiao_user001",
  "data": "{\"_lctype\":1,\"_lcattrs\":{\"msg_id\":\"client_1710001111222_abc123\",\"from_qiao_id\":\"qiao_user001\",\"to_qiao_id\":\"qiao_xm001\",\"conversation_id\":\"conv_xyz789\",\"content\":\"你好\",\"message_type\":1,\"supports_typing\":true,\"sent_time\":1710001111222}}",
  "timestamp": 1710001111333,
  "ack": true
}
```

**字段说明**:

- `msgId` (string) - LeanCloud 生成的消息 ID，用于 `msg_id_provider_inbound`
- `conv.objectId` (string) - LeanCloud 系统对话 ID，必须与 `lc-im/config` 返回值一致
- `data` (string/object) - TypedMessage JSON，服务端解析 `_lcattrs`
- `from` (string) - LeanCloud 侧的发送者 client_id
- `timestamp` (integer) - LeanCloud 创建消息的时间（毫秒）
- 其他字段参考 LeanCloud 官方 Webhook 文档

### 内层 `_lcattrs` 规范

Webhook 解析后得到的 `_lcattrs` 为 LeanCloud Provider 入站载荷；服务端会将其映射为内部事件结构（见 `../spec/message/schema.md`）：

| 字段 | 说明 |
| --- | --- |
| `msg_id` | 客户端生成的消息 ID |
| `from_qiao_id` / `to_qiao_id` | 发送方 / 接收方外部 ID |
| `conversation_id` | 系统内部对话 ID |
| `content` | 文本内容，若 `metadata.encryption` 存在需解密 |
| `message_type` | 消息类型：1=TEXT，2/3=Typing，4=ChatInfo，9=Notification |
| `supports_typing` | 客户端是否支持输入状态 |
| `sent_time` | 客户端发送时间（毫秒） |
| `action` / `notification_type` / `data` | 系统消息附带的数据 |
| `encryption` / `enc_version` | 传输加密元数据 |

### 响应

**200 OK**

```json
{ "code": 200 }
```

服务端始终返回 `{ "code": 200 }`。

### 安全基线

- 统一使用 `POST /api/v1/leancloud/webhook/{webhook_token}`，路径令牌由后端生成
- 校验 `conv.objectId` 与系统配置中的 `im_conv_id` 一致
- `msgId` 写入 `msg_id_provider_inbound`，重复上报直接丢弃。

### 业务说明

- Webhook 只负责将 LeanCloud payload 解析为内部 `InboundMessageEvent`，具体业务逻辑见 `docs/spec/message/README.md`
- 如果解密失败或对话不存在，服务端会记录日志并返回 200（LeanCloud 按成功处理），同时向监控告警
