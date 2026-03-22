# LeanCloud 集成

本文档说明如何与 LeanCloud 即时通讯服务集成，包括 Webhook 处理、消息解析。

## 架构设计

LeanCloud 作为消息传输层，与系统解耦。

### 设计原则

- LeanCloud 只负责消息传输，不承载业务逻辑
- 使用全局唯一的系统对话 ID
- 后端使用 REST API 调用
- 小程序使用 Java SDK 调用
- 所有接口隐藏第三方实现细节

说明：

- 消息传输层支持多个 Provider：LeanCloud（本文件）与 WebSocket（管理端测试页，见 `websocket.md`）
- 不同 Provider 的传输格式不同，但服务端必须统一转换为内部 `InboundMessageEvent`（见 `schema.md`）
- dispatch 在 LeanCloud 场景使用 USER 粒度 endpoint；`target_key` 对应 LeanCloud `client_id`（当前系统等同 `qiao_id`）

### 系统对话

所有消息都在一个 LeanCloud 系统对话中发送：

- 对话 ID 存储在 system_configs 表（`leancloud_im_service_conversation_id`）
- 客户端启动时通过 `/api/v1/lc-im/config` 获取
- 可随时变更，客户端应在重连时主动拉取
- `im_conv_id` 的权威来源是 `/api/v1/lc-im/config`

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
    "conversation_id": "conv_xyz789",
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
4. 连接成功后，通过独立 Presence 接口注册/续租 LeanCloud USER endpoint（`target_key=client_id`）

说明：

- `lc-im/signature` 只负责 LeanCloud 登录签名，不负责 `message_endpoints` 注册。

### USER endpoint 注册与续租

- LeanCloud 使用 USER 粒度 endpoint（`endpoint_scope=USER`，`device_id=NULL`）。
- `target_key` 固定为 LeanCloud `client_id`（当前系统等同 `qiao_id`）。
- 注册/续租接口：`POST /api/v1/lc-im/presence`。
- LeanCloud Presence 与 WebSocket Presence 在后端共用统一 upsert 服务（内部统一，入口按 provider 保持分离）。
- SDK 建连成功后必须触发 endpoint 注册；会话期间按 lease 续租。
- dispatch 仅面向活跃 endpoint 派发，禁止依赖签名接口隐式注册 endpoint。

## 消息发送

### 发送流程

**逻辑步骤**：

1. dispatch 选择 provider=LeanCloud 的目标 endpoint（USER 粒度）
2. 使用 endpoint `target_key`（client_id）组装 `to_clients`
3. 加密 content（如果需要）
4. 构建 TypedMessage 格式
5. 调用 LeanCloud REST API
6. 返回 LeanCloud 消息 ID
7. 写入 `message_deliveries.provider_msg_id`（由 dispatch worker 在 delivery 记录中维护）

### Typing（transient）

- `message_type=2|3`（TYPING_START / TYPING_END）为 realtime best-effort 事件。
- Typing 通过 LeanCloud 传输时，按 `transient=true` 发送。

### TypedMessage `_lcattrs` 出站字段语义

- `msg_id`：时间线消息 `msg_id_server`。
- `msg_id_client`：可选字段；当该时间线消息来自用户入站时回传原客户端 ID。
- assistant/系统消息：`msg_id_client` 为空或省略。

## 配置管理

### system_configs 配置项

- leancloud_im_server_url - LeanCloud IM server URL
- leancloud_im_service_conversation_id - 系统对话 ID
- leancloud_im_webhook_token - Webhook 安全令牌
- api_base_url - API base URL（用于构造 webhook URL）

### 发送错误

- 网络错误 → 写入 message_deliveries（failed/pending），进入重试调度
- LeanCloud 服务异常 → 写入 message_deliveries（failed/pending），进入重试调度
- 消息格式错误 → 记录日志，告警，不重试

详见 [failure-handling.md](failure-handling.md)
