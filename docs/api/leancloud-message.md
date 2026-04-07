# LeanCloud 接口

LeanCloud 相关接口分为两类：
- 客户端会话编排接口（`lc-im` 命名空间）
- LeanCloud 服务端回调接口（`leancloud` 命名空间）

## 接口列表

- [会话引导（Bootstrap）](#会话引导bootstrap) - `POST /api/v1/lc-im/bootstrap`
- [LeanCloud 消息 Webhook](#leancloud-消息-webhook) - `POST /api/v1/leancloud/webhook/{webhook_token}`

---

## 会话引导（Bootstrap）

### 基本信息

- **路径**: `POST /api/v1/lc-im/bootstrap`
- **认证**: Bearer Token（必需）
- **说明**: 一次返回客户端建连所需全部信息，并由服务端完成会话可用性校验与用户会话订阅

### 请求体

```json
{
  "client_kind": 2
}
```

**字段说明**:

- `client_kind` (integer, 可选) - 客户端类型（web/miniprogram/ios/android）

### 成功响应 (200)

```json
{
  "config_version": "2026-04-07T11:00:00Z",
  "session": {
    "client_id": "qiao_user001",
    "app_id": "1D3xXb5zGCKUfQOb4A0Mb4V5-gzGzoHsz",
    "app_key": "rHhmsllHS0y4zFBCiwLe4WSC",
    "server_url": "https://chat.qiaoqiaoai.cn",
    "im_conv_id": "69c1113b1dc6aa415111cc49",
    "signature": {
      "algorithm": "HMAC-SHA1",
      "version": "v1",
      "value": "hmac_sha1_signature",
      "timestamp": 1710001111000,
      "nonce": "random_nonce_string",
      "expires_in_ms": 3600000
    }
  },
  "presence": {
    "endpoint_id": 223788765171155062,
    "lease_ttl_days": 365,
    "lease_expires_at_ms": 1793808000000
  }
}
```

**字段说明**:

- `config_version` (string) - 当前会话配置版本，客户端用于判断是否需要重建连接
- `session.client_id` (string) - LeanCloud client_id，等于当前登录用户 `qiao_id`
- `session.app_id` (string) - LeanCloud App ID
- `session.app_key` (string) - LeanCloud App Key（客户端建连参数，不是服务端机密）
- `session.server_url` (string) - LeanCloud Server URL
- `session.im_conv_id` (string) - 系统对话 ID
- `session.signature.*` - SDK 登录签名信息
- `presence.*` - USER 粒度 endpoint 注册/续租结果

### 服务端行为（强制）

1. 校验并加载 LeanCloud 运行配置。
2. 校验系统会话 `im_conv_id` 存在且可用，不可用则拒绝返回成功。
3. 确保当前用户已订阅系统会话（subscriber 存在）。
4. 生成登录签名。
5. upsert 并续租 USER endpoint。
6. 返回完整会话引导响应。

### 错误响应

**400 Bad Request**:

- `"参数错误"` - 请求体字段不合法

**401 Unauthorized**:

- `"认证失效，请重新登录"` - Token 无效或已过期

**500 Internal Server Error**:

- `"系统错误"` - 配置缺失、会话不可用、订阅失败、签名失败、presence 写入失败等

### 客户端约束

- 客户端必须以本接口返回值初始化 LeanCloud SDK，禁止本地硬编码 `app_id/app_key/server_url/im_conv_id`。
- `config_version` 变化时，客户端必须清理本地会话缓存并重建连接。

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
  "conv": { "objectId": "69c1113b1dc6aa415111cc49" },
  "from": "qiao_user001",
  "data": "{\"_lctype\":1,\"_lcattrs\":{\"msg_id\":\"client_1710001111222_abc123\",\"from_qiao_id\":\"qiao_user001\",\"to_qiao_id\":\"qiao_xm001\",\"conversation_id\":\"conv_xyz789\",\"content\":\"你好\",\"message_type\":1,\"supports_typing\":true,\"sent_time\":1710001111222}}",
  "timestamp": 1710001111333,
  "ack": true
}
```

**字段说明**:

- `msgId` (string) - LeanCloud 生成的消息 ID，用于 `msg_id_provider_inbound`
- `conv.objectId` (string) - LeanCloud 系统对话 ID，必须与服务端当前生效 `im_conv_id` 一致
- `data` (string/object) - TypedMessage JSON，服务端解析 `_lcattrs`
- `from` (string) - LeanCloud 侧发送者 client_id
- `timestamp` (integer) - LeanCloud 创建消息时间（毫秒）

### 响应

**200 OK**

```json
{ "code": 200 }
```

### 安全基线

- 统一使用 `POST /api/v1/leancloud/webhook/{webhook_token}`，路径令牌由后端生成。
- 校验 `conv.objectId` 与服务端配置中的 `im_conv_id` 一致。
- `msgId` 写入 `msg_id_provider_inbound`，重复上报直接丢弃。
