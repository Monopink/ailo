# LeanCloud 集成

本文档说明如何与 LeanCloud 即时通讯服务集成，包括 Webhook 处理、消息解析。

## 架构设计

LeanCloud 作为消息传输层，与系统解耦，便于未来替换。

### 设计原则

- LeanCloud 只负责消息传输，不承载业务逻辑
- 使用全局唯一的系统对话 ID
- 后端使用 REST API 调用
- 小程序使用 Java SDK 调用
- 所有接口隐藏第三方实现细节

### 系统对话

所有消息都在一个 LeanCloud 系统对话中发送：

- 对话 ID 存储在 system_configs 表（`leancloud_im_conv_id`）
- 客户端启动时通过 `/api/v1/lc-im/config` 获取
- 可随时变更，客户端应在重连时主动拉取

## Webhook 处理

### 接口定义

完整接口定义见 [api/leancloud-message.md](../../api/leancloud-message.md#leancloud-消息-webhook)

**路径**：`POST /api/v1/leancloud/webhook/{webhook_token}`

### 安全验证

**路径参数验证**：

- `webhook_token` 由服务端生成，存储在 system_configs
- LeanCloud 配置中填入完整 URL

### Webhook Payload 解析

**外层结构**：

```json
{
  "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
  "conv": { "objectId": "68edda0a554ecc6e8843b246" },
  "from": "qiao_user001",
  "data": "{...}",
  "timestamp": 1710001111333,
  "ack": true
}
```

**字段说明**：

- msgId - LeanCloud 生成的消息 ID，写入 `msg_id_provider_inbound`
- conv.objectId - LeanCloud 对话 ID，必须与配置一致
- data - TypedMessage JSON，需解析 `_lcattrs`
- from - LeanCloud 侧的发送者 client_id
- timestamp - LeanCloud 创建消息的时间（毫秒）

**内层 _lcattrs 解析**：

```json
{
  "_lctype": 1,
  "_lcattrs": {
    "msg_id": "client_1710001111222_abc123",
    "from_qiao_id": "qiao_user001",
    "to_qiao_id": "qiao_xm001",
    "conv_id": "conv_xyz789",
    "content": "你好",
    "message_type": 1,
    "supports_typing": true,
    "sent_time": 1710001111222,
    "encryption": "base64",
    "enc_version": "v1"
  }
}
```

详见 [schema.md](schema.md)

### 处理流程

**逻辑步骤**：

1. 验证 webhook_token
2. 验证 conv.objectId
3. 解析 data 字段
4. 解密 content（如果有 encryption）
5. 转换为 InboundMessageEvent
6. 调用消息服务核心处理
9. 返回 `{"success": true}`

### 重复消息处理

**去重逻辑**：

通过 `msgId` 检查 message_history 表中的 msg_id_provider_inbound 字段：

- 如果已存在 → 重复上报，直接返回成功
- 如果不存在 → 正常处理

## 客户端签名

### 接口定义

完整接口定义见 [api/leancloud-message.md](../../api/leancloud-message.md#获取-leancloud-客户端签名)

**路径**：`POST /api/v1/lc-im/signature`

### 签名生成

**算法**：HMAC-SHA1

**输入**：

- client_id（用户的 qiao_id）
- timestamp（当前时间戳，毫秒）
- nonce（随机字符串）
- app_secret（LeanCloud 密钥）

**计算**：

```
message = client_id + timestamp + nonce
signature = HMAC_SHA1(app_secret, message)
```

**返回**：

- signature - 签名字符串
- timestamp - 时间戳
- nonce - 随机数
- expires_in - 有效期（秒）

### 客户端使用

**流程**：

1. 客户端调用 `/api/v1/lc-im/signature` 获取签名
2. 使用返回的 signature、timestamp、nonce 连接 LeanCloud SDK
3. LeanCloud SDK 验证签名后建立连接

## 消息发送

### 发送流程

**逻辑步骤**：

1. 加密 content（如果需要）
2. 构建 TypedMessage 格式
3. 调用 LeanCloud REST API
4. 返回 LeanCloud 消息 ID
5. 写入 msg_id_provider_outbound

### REST API 调用

**端点**：`POST https://api.leancloud.cn/1.1/rtm/messages`

**请求头**：

- X-LC-Id: {app_id}
- X-LC-Key: {app_key}
- Content-Type: application/json

**请求体**：

```json
{
  "from_peer": "qiao_xm001",
  "conv_id": "68edda0a554ecc6e8843b246",
  "transient": false,
  "message": {
    "_lctype": 1,
    "_lcattrs": {
      "msg_id": "223788765171154945",
      "from_qiao_id": "qiao_xm001",
      "to_qiao_id": "qiao_user001",
      "conv_id": "conv_xyz789",
      "content": "你好",
      "message_type": 1,
      "sent_time": 1710001111222
    }
  }
}
```

### 发送结果处理

**成功响应**：

```json
{
  "msg-id": "xYz9iBSBS_uogCEgvZwE8R",
  "timestamp": 1710001111333
}
```

**后续操作**：

将返回的 msg-id 写入 message_history.msg_id_provider_outbound

## 配置管理

### system_configs 配置项

- leancloud_app_id - LeanCloud App ID
- leancloud_app_key - LeanCloud App Key
- leancloud_master_key - LeanCloud Master Key
- leancloud_im_conv_id - 系统对话 ID
- leancloud_webhook_token - Webhook 安全令牌
- leancloud_signature_ttl_ms - 签名有效期（毫秒）

### 配置获取

**返回格式**：

```json
{
  "provider": "leancloud",
  "im_conv_id": "68edda0a554ecc6e8843b246",
  "signature_algorithm": "HMAC-SHA1",
  "signature_version": "v1",
  "signature_ttl_ms": 3600000
}
```

## 安全基线

### 必须实施

- ✅ 验证 webhook_token（路径参数）
- ✅ 验证 conv.objectId 与配置一致
- ✅ msgId 去重（防止重复处理）

### 建议实施

- 网关层 IP 白名单
- WAF 规则
- 速率限制
- 异常告警

## 错误处理

### Webhook 错误

**处理原则**：Webhook 必须返回 200，否则 LeanCloud 会重试

- webhook_token 无效 → 返回 200，记录日志，告警
- payload 格式错误 → 返回 200，记录日志，告警
- 对话 ID 不匹配 → 返回 200，记录日志，告警
- 解密失败 → 返回 200，记录日志，回退到原文
- 业务处理失败 → 返回 200，记录日志，写入失败表

### 发送错误

- 网络错误 → 写入 message_delivery_failures，重试
- LeanCloud 服务异常 → 写入 message_delivery_failures，重试
- 消息格式错误 → 记录日志，告警，不重试

详见 [failure-handling.md](failure-handling.md)

## 未来替换方案

如果需要切换消息服务提供商：

1. 实现新的 provider 模块（如 `providers/tencent_im/`）
2. 实现相同的接口（send_message, handle_webhook）
3. 更新 system_configs 中的 provider 配置
4. 客户端通过 `/api/v1/lc-im/config` 获取新配置
5. 无需修改其他业务代码

**接口抽象**：

```
MessageProvider 接口：
  - send_message() - 发送消息
  - handle_webhook() - 处理回调
  - generate_signature() - 生成签名
```
