# 消息数据结构

本文档定义消息系统的数据结构，包括传输格式、Event定义、消息ID规则。

## Provider 与传输格式

消息系统支持多个消息传输 Provider。不同 Provider 的“线上传输格式”不同，但在服务端落地后都必须转换为统一的内部事件结构（见下文“消息事件 Schema”）。

- LeanCloud Provider：TypedMessage 格式（见本文件“LeanCloud 传输格式”）
- WebSocket Provider：JSON 消息格式（见 `websocket.md`）

## LeanCloud 传输格式

客户端与服务端通过 LeanCloud 系统对话传输消息，使用 TypedMessage 格式。

说明：

- 统一业务定位键为 `conversation_id`（等于 contacts.conversation_id）。
- LeanCloud 传输载荷（`_lcattrs`）也统一使用 `conversation_id`；服务端转换为内部事件结构时保持同名字段。

### 基本结构

```json
{
  "msg_id": "client_1710001111222_abc123",
  "from_qiao_id": "qiao_user001",
  "to_qiao_id": "qiao_xm001",
  "conversation_id": "conv_xyz789",
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
- conversation_id (string, 必填) - 对话ID（后端管理）
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

### Typing（transient）

LeanCloud 侧的 `transient` 为传输层选项，不属于 `_lcattrs` 字段。

- `message_type=2|3`（TYPING_START / TYPING_END）必须以 `transient=true` 发送。

## WebSocket 传输格式

WebSocket Provider 的传输载荷统一为 JSON；客户端以 `device_id` 作为稳定标识。详细协议见：

- `websocket.md`

原则：

- WS 传输层不承载业务逻辑，只负责把客户端消息转换为内部 `InboundMessageEvent`
- 服务端推送消息时，统一以内部事件或其等价字段输出（便于测试页实时渲染）
- 自研通道（WebSocket）允许 `msg_id_provider_inbound` 为空；第三方通道必须填写
 - 客户端标识为 `device_id`；服务端内部路由/投递目标以 Presence endpoint（`endpoint_id`）为准，禁止仅用 `device_id` 作为内部路由键（避免多账号复用同一 device_id 时串线）
- 代码目录分层：provider sender 位于 `services/message/providers/websocket/*`；连接与状态管理位于 `services/message/websocket/*`
- WS 入站字段适配（payload -> `InboundMessageEvent`）位于 `services/message/providers/websocket/*`；API 层仅处理帧级协议与鉴权。

## 消息ID设计

### 双 ID 语义

消息系统使用 `msg_id_server` 与 `msg_id_client` 两个 ID 字段，职责固定：

- `msg_id_server`：服务端生成的时间线唯一标识（inbound/outbound 均有值），用于客户端去重与 ACK。
- `msg_id_client`：客户端生成的消息 ID，用于入站幂等与发送端本地对齐（仅用户侧消息有值）。

### ID生成规则

**用户发送的消息**：

- `msg_id_client` 由客户端生成
- 格式：`client_{timestamp}_{random}`
- 示例：`client_1710001111222_abc123`
- 用途：去重、状态追踪、失败重试

- 服务端接收入站消息落库时，会为该时间线消息生成 `msg_id_server`（形如 `msg_{snowflake}`），用于对外推送、离线拉取与 HTTP ACK。

**AI/系统发送的消息**：

- `msg_id_server` 由服务端生成（Snowflake ID）
- 格式：`msg_{snowflake}`
- 示例：`msg_223788765171154945`
- 用途：服务端消息管理和查询

### 数据库存储映射

message_history 表存储多个ID字段（完整定义见 [message.md](../../data-dict/message.md)）：

- msg_id_server - 服务端统一生成的消息ID（形如 `msg_{snowflake}`）- 示例：`msg_223788765171154945`
- msg_id_client - 客户端生成的ID（仅用户消息有值）- 示例：`client_1710001111222_abc123`
- msg_id_provider_inbound - 第三方入站消息ID（第三方通道必填，自研通道可为空）- 示例：`nYH9iBSBS_uogCEgvZwE7Q`
- Provider 出站回执 - 统一记录在 `message_deliveries.provider_msg_id`（不再存入 `message_history`）

### 使用场景

- 客户端发送用户消息 → 生成 `msg_id_client`
- 服务端接收入站消息 → 生成 `msg_id_server` 并保留 `msg_id_client`
- 服务端发送 AI/系统消息 → 生成 `msg_id_server`，`msg_id_client` 为空
- 客户端接收时间线事件 → 以 `msg_id_server` 去重并推进 ACK
- 客户端重试发送同一消息 → 复用 `msg_id_client` 触发服务端幂等

## 消息事件 Schema

系统在 Webhook → 管线 → 缓冲/AI → 发送 各阶段共享统一的事件结构。

### 版本与命名

- `schema_version`: 当前版本 `1.0.0`（语义化版本号）
- `event_type`: 小写蛇形命名（`inbound_message` / `outbound_message`）
- 所有时间均为 Unix 毫秒时间戳
- 所有身份字段使用 `qiao_id`（对外ID）

### 公共字段

说明：

- 对外事件/接口中的时间戳字段统一为 UTC 的 Unix epoch 毫秒时间戳；服务端落库可使用 `TIMESTAMP WITH TIME ZONE`。

- schema_version (string, 必填) - 文档版本 `1.0.0`
- event_type (string, 必填) - `inbound_message` / `outbound_message`
- message_type (int, 必填) - 消息类别（1=TEXT, 2=TYPING_START, 3=TYPING_END, 4=CHAT_INFO, 9=NOTIFICATION）
- conversation_id (string, 必填) - 对话ID（DB: message_history.conversation_id）
- from_qiao_id (string, 必填) - 发送方 qiao_id
- to_qiao_id (string, 必填) - 接收方 qiao_id
- content (string, 必填) - 文本内容（typing 类可为空）
- sent_time_ms (int, 必填) - 发送时间（毫秒）
- sent_time_ms 由服务端认定（用于排序、离线游标推进与审计）；client_sent_time_ms 仅为客户端上送时间（用于展示/调试）。
- msg_id_server (string, 必填) - 服务端消息ID（形如 `msg_{snowflake}`）
- msg_id_client (string/null, 条件必填) - 客户端ID（仅用户消息必填）
- msg_id_provider_inbound (string/null, 条件必填) - 第三方入站ID（第三方通道必填，自研通道可为空）
- supports_typing (bool, 条件必填) - 客户端是否支持 typing（入站消息必填；出站事件/接口可省略）
- client_sent_time_ms (int/null, 条件必填) - 客户端发送时间（Unix 毫秒时间戳，UTC）
- metadata (object, 必填) - 业务扩展字段

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
  "sent_time_ms": 1710001111222,
  "msg_id_server": "msg_223788765171154945",
  "msg_id_client": "client_1710001111222_abc123",
  "msg_id_provider_inbound": "nYH9iBSBS_uogCEgvZwE7Q",
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
  "sent_time_ms": 1710002222333,
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

- 该字段是“客户端能力标记”，主要用于入站消息驱动 buffer 策略；服务端对外推送/接口响应中可省略。
- true - 支持输入状态（小程序）- 使用智能缓冲（双计时器）
- false/null - 不支持输入状态（公众号）- 使用 NO_TYPING_WAIT 策略

详见 [buffer.md](buffer.md)

## 数据库表关系

数据库表结构与字段定义见 [data-dict/message.md](../../data-dict/message.md)。本文避免重复列出字段，仅说明关系与不变量：

- `message_history`：消息事实（不承载投递状态）
- `message_dispatch_outbox`：记录待派发任务（重试与恢复入口）
- `message_deliveries`：按 endpoint 维度记录投递结果（每 endpoint 一条结果）
- `message_devices`：按 (user_id, device_id) 维度管理离线游标与活跃信息
- `message_endpoints`：管理可投递端点，支持 USER/DEVICE 双粒度（不强制所有 provider 同粒度）；`target_key` 为 provider 投递地址（WebSocket=device_id，LeanCloud=client_id/qiao_id）
