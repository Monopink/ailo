# 消息数据结构

本文档定义消息系统的数据结构，包括传输格式、Event定义、消息ID规则。

## LeanCloud 传输格式

客户端与服务端通过 LeanCloud 系统对话传输消息，使用 TypedMessage 格式。

### 基本结构

```json
{
  "msg_id": "client_1710001111222_abc123",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "conv_id": "conv_xyz789",
  "content": "你好",
  "message_type": 1,
  "supports_typing": true,
  "sent_time": 1710001111222
}
```

### 字段说明

- msg_id (string, 必填) - 消息ID（客户端生成或服务端生成）
- from_qiao_id (string, 必填) - 发送者 qiao_id
- to_qiao_id (string, 必填) - 接收者 qiao_id
- conv_id (string, 必填) - 对话ID（后端管理）
- content (string, 必填) - 消息内容（typing 类可为空）
- message_type (int, 必填) - 消息类型（见下文）
- supports_typing (bool, 必填) - 客户端是否支持输入状态
- sent_time (int, 必填) - 发送时间戳（毫秒）

### 消息类型枚举

- TEXT (1) - 文本消息
- TYPING_START (2) - 开始输入
- TYPING_END (3) - 结束输入
- CHAT_INFO (4) - 对话提示信息
- NOTIFICATION (9) - 系统通知

## 消息ID设计

### 单一ID字段原则

消息使用单一的 `msg_id` 字段，通过消息方向判断ID类型。

### ID生成规则

**用户发送的消息**：

- `msg_id` 由客户端生成
- 格式：`client_{timestamp}_{random}`
- 示例：`client_1710001111222_abc123`
- 用途：去重、状态追踪、失败重试

**AI/系统发送的消息**：

- `msg_id` 由服务端生成（Snowflake ID）
- 格式：数字ID
- 示例：`223788765171154945`
- 用途：服务端消息管理和查询

**转发消息**：

- 保持原始 `msg_id` 不变
- 用户A → 服务端 → 用户B，`msg_id` 始终是用户A生成的客户端ID
- 服务端只生成 `msg_id_server` 用于数据库存储

### 数据库存储映射

message_history 表存储多个ID字段（完整定义见 [message.md](../../data-dict/message.md)）：

- msg_id_server - 服务端统一生成的 Snowflake ID（主键）- 示例：`223788765171154945`
- msg_id_client - 客户端生成的ID（仅用户消息有值）- 示例：`client_1710001111222_abc123`
- msg_id_provider_inbound - LeanCloud 入站消息ID - 示例：`nYH9iBSBS_uogCEgvZwE7Q`
- msg_id_provider_outbound - LeanCloud 出站确认ID（发送成功后回填）- 示例：`xYz9iBSBS_uogCEgvZwE8R`

### 使用场景

- 客户端发送消息 → 生成 `msg_id`（客户端ID）
- 服务端接收消息 → 生成 `msg_id_server`，保持 `msg_id` 不变
- 服务端发送消息 → 生成 `msg_id`（服务端ID）
- 消息发送失败 → 通过 `msg_id` 标识失败的消息
- 消息重试 → 使用 `msg_id` 避免重复发送

## 消息事件 Schema

系统在 Webhook → 管线 → 缓冲/AI → 发送 各阶段共享统一的事件结构。

### 版本与命名

- `schema_version`: 当前版本 `1.0.0`（语义化版本号）
- `event_type`: 小写蛇形命名（`inbound_message` / `outbound_message`）
- 所有时间均为 Unix 毫秒时间戳
- 所有身份字段使用 `qiao_id`（对外ID）

### 公共字段

- schema_version (string, 必填) - 文档版本 `1.0.0`
- event_type (string, 必填) - `inbound_message` / `outbound_message`
- message_type (int, 必填) - 消息类别（1=TEXT, 2=TYPING_START, 3=TYPING_END, 4=CHAT_INFO, 9=NOTIFICATION）
- conversation_id (string, 必填) - 系统内部 conv_id
- from_qiao_id (string, 必填) - 发送方 qiao_id
- to_qiao_id (string, 必填) - 接收方 qiao_id
- content (string, 必填) - 文本内容（typing 类可为空）
- sent_at_ms (int, 必填) - 发送时间（毫秒）
- msg_id_server (string, 必填) - 服务端 Snowflake ID
- msg_id_client (string/null, 条件必填) - 客户端ID（仅用户消息必填）
- msg_id_provider_inbound (string/null, 条件必填) - LeanCloud 入站ID
- msg_id_provider_outbound (string/null, 条件必填) - LeanCloud 出站ID
- supports_typing (bool, 必填) - 客户端是否支持 typing
- client_sent_time (int/null, 条件必填) - 客户端发送时间
- metadata (object, 必填) - 业务扩展字段
- provider_metadata (object, 必填) - 第三方原始字段

### metadata 白名单

- action - 系统消息附带的 action 描述
- notification_type - 通知类型枚举
- rate_limit_bucket - 速率限制统计窗口
- encryption - 传输加密算法
- encryption_version - 加密版本

### InboundMessageEvent 示例

```json
{
  "schema_version": "1.0.0",
  "event_type": "inbound_message",
  "message_type": 1,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "content": "你好",
  "sent_at_ms": 1710001111222,
  "msg_id_server": "msg_223788765171154945",
  "msg_id_client": "client_1710001111222_abc123",
  "msg_id_provider_inbound": "nYH9iBSBS_uogCEgvZwE7Q",
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": 1710001111222,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_from": "qiao_user001",
    "lc_conv_id": "68edda0a554ecc6e8843b246"
  }
}
```

### OutboundMessageEvent 示例

```json
{
  "schema_version": "1.0.0",
  "event_type": "outbound_message",
  "message_type": 1,
  "conversation_id": "conv_xyz789",
  "from_qiao_id": "qiao_xm001",
  "to_qiao_id": "qiao_user001",
  "content": "我在呢，刚才看到你发的消息啦～",
  "sent_at_ms": 1710002222333,
  "msg_id_server": "msg_223788765171155999",
  "msg_id_client": null,
  "msg_id_provider_inbound": null,
  "msg_id_provider_outbound": null,
  "supports_typing": true,
  "client_sent_time": null,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
  },
  "provider_metadata": {
    "lc_conv_id": "68edda0a554ecc6e8843b246"
  }
}
```

## supports_typing 字段

标识客户端是否支持输入状态，影响缓冲策略。

- true - 支持输入状态（小程序）- 使用智能缓冲（双计时器）
- false/null - 不支持输入状态（公众号）- 使用 NO_TYPING_WAIT 策略

详见 [buffer.md](buffer.md)

## 数据库表关系

完整表结构见 [data-dict/message.md](../../data-dict/message.md)

### message_history

存储所有成功发送的消息。

**关键字段**：

- `msg_id_server`: 主键（Snowflake ID）
- `msg_id_client`: 客户端ID（用户消息）
- `msg_id_provider_inbound`: LeanCloud 入站ID
- `msg_id_provider_outbound`: LeanCloud 出站ID
- `direction`: 消息方向（1=inbound, 2=outbound）
- `message_type`: 消息类型
- `content`: 消息内容
- `message_metadata`: 元数据JSON（包含 encryption 等）
- `provider_metadata`: 第三方原始 payload

### message_delivery_failures

存储发送失败的消息，成功重发后删除。

**关键字段**：

- `msg_id_server`: 原消息ID
- `msg_id_provider`: 第三方出站消息ID
- `content`: 消息内容
- `fail_reason_code`: 失败原因代码
- `retry_count`: 重试次数
- `next_retry_at`: 下次重试时间

详见 [failure-handling.md](failure-handling.md)
