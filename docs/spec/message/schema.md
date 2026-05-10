# 消息数据结构

本文档定义消息系统的数据结构，包括传输格式、事件结构与消息 ID 规则。

## Provider 与传输格式

消息系统使用 Provider 抽象承载传输层；不同 Provider 的线上格式可以不同，但服务端落地前必须转换为统一内部事件结构（见下文“消息事件 Schema”）。

当前用户消息实时通道为 WebSocket，传输格式为 JSON（详见 `websocket.md`）。

原则：

- 传输层不承载业务逻辑，只负责鉴权后的消息收发与事件适配
- 服务端内部统一进入 `InboundMessageEvent`
- 自研通道允许 `msg_id_provider_inbound` 为空；第三方回调型通道必须填写
- 客户端标识为 `device_id`；服务端内部路由/投递目标以 Presence endpoint（`endpoint_id`）为准

## 消息 ID 设计

### 双 ID 语义

消息系统使用 `msg_id_server` 与 `msg_id_client` 两个 ID 字段，职责固定：

- `msg_id_server`：服务端生成的时间线唯一标识（inbound/outbound 均有值），用于客户端去重与 ACK
- `msg_id_client`：客户端生成的消息 ID，用于入站幂等与发送端本地对齐（仅用户侧消息有值）

### ID 生成规则

用户发送的消息：

- `msg_id_client` 由客户端生成
- 格式：`client_{timestamp}_{random}`
- 示例：`client_1710001111222_abc123`
- 用途：去重、状态追踪、失败重试

服务端接收入站消息落库时：

- 为时间线消息生成 `msg_id_server`（形如 `msg_{snowflake}`）
- 用于对外推送、离线拉取与 HTTP ACK

AI/系统发送的消息：

- `msg_id_server` 由服务端生成（Snowflake ID）
- 格式：`msg_{snowflake}`
- 示例：`msg_223788765171154945`

### 数据库存储映射

涉及数据表：`message_history`

- `msg_id_server`：服务端统一生成的消息 ID
- `msg_id_client`：客户端生成的 ID（仅用户消息有值）
- `msg_id_provider_inbound`：第三方入站消息 ID（第三方通道必填，自研通道可为空）
- Provider 出站回执：记录在 `message_deliveries.provider_msg_id`

### 使用场景

- 客户端发送用户消息：生成 `msg_id_client`
- 服务端接收入站消息：生成 `msg_id_server` 并保留 `msg_id_client`
- 服务端发送 AI/系统消息：生成 `msg_id_server`，`msg_id_client` 为空
- 客户端接收时间线事件：以 `msg_id_server` 去重并推进 ACK
- 客户端重试发送同一消息：复用 `msg_id_client` 触发服务端幂等

## 消息事件 Schema

系统在 WebSocket 入站、管线处理、缓冲/AI、发送各阶段共享统一事件结构。

说明：

- 本节定义服务端内部事件结构（pipeline）
- 对外接口（HTTP 离线拉取、WebSocket 推送）的字段名以对应 API 文档为准

### 版本与命名

- `schema_version`：当前版本 `1.0.0`
- `event_type`：小写蛇形命名（`inbound_message` / `outbound_message`）
- 所有时间均为 Unix 毫秒时间戳
- 所有身份字段使用 `qiao_id`

### 公共字段

说明：

- 时间戳值统一为 UTC 的 Unix epoch 毫秒时间戳（整数）；对外 API 的时间字段命名规范见 `../time-format.md`

- `schema_version` (string, 必填) - 文档版本 `1.0.0`
- `event_type` (string, 必填) - `inbound_message` / `outbound_message`
- `message_type` (int, 必填) - 消息类别（1=TEXT, 2=TYPING_START, 3=TYPING_END, 4=CHAT_INFO, 9=NOTIFICATION）
- `conversation_id` (string, 必填) - 对话 ID（DB: `message_history.conversation_id`）
- `from_qiao_id` (string, 必填) - 发送方 qiao_id
- `to_qiao_id` (string, 必填) - 接收方 qiao_id
- `content` (string, 必填) - 文本内容（typing 类可为空）
- `sent_at_ms` (int, 必填) - 事件时间（毫秒，内部事件结构字段名；对外等价字段名为 `sent_time_ms`）
- `msg_id_server` (string, 必填) - 服务端消息 ID
- `msg_id_client` (string/null, 条件必填) - 客户端 ID（仅用户消息必填）
- `msg_id_provider_inbound` (string/null, 条件必填) - 第三方入站 ID（第三方通道必填，自研通道可为空）
- `supports_typing` (bool, 条件必填) - 客户端是否支持 typing（入站消息必填；出站事件/接口可省略）
- `client_sent_time_ms` (int/null, 条件必填) - 客户端发送时间（Unix 毫秒时间戳，UTC）
- `metadata` (object, 必填) - 业务扩展字段

### metadata 白名单

- `action` - 系统消息附带的 action 描述
- `notification_type` - 通知类型枚举
- `rate_limit_bucket` - 速率限制统计窗口
- `encryption` - 传输加密算法
- `encryption_version` - 加密版本

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
  "msg_id_provider_inbound": null,
  "supports_typing": true,
  "client_sent_time_ms": 1710001111222,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
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
  "client_sent_time_ms": null,
  "metadata": {
    "encryption": "base64",
    "encryption_version": "v1"
  }
}
```

## supports_typing 字段

标识客户端是否支持输入状态，影响缓冲策略。

- 该字段是客户端能力标记，主要用于入站消息驱动 buffer 策略
- `true`：支持输入状态，使用智能缓冲（双计时器）
- `false/null`：不支持输入状态，使用 `NO_TYPING_WAIT` 策略

详见 [buffer.md](buffer.md)

## 数据库表关系

数据库表结构与字段定义涉及：`message_history`, `message_dispatch_outbox`, `message_deliveries`, `message_devices`, `message_endpoints`。本文仅说明关系与不变量：

- `message_history`：消息事实（不承载投递状态）
- `message_dispatch_outbox`：记录待派发任务（重试与恢复入口）
- `message_deliveries`：按 endpoint 维度记录投递结果（每 endpoint 一条结果）
- `message_devices`：按 `(user_id, device_id)` 维度管理离线游标与活跃信息
- `message_endpoints`：管理可投递端点，支持 USER/DEVICE 双粒度；`target_key` 为 provider 投递地址（WebSocket=`device_id`）
