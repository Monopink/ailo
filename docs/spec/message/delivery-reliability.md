# 离线消息补齐与 ACK

离线消息用于断联期间消息补齐。

## 设计目标

- **离线消息**：仅补齐断联期间未接收的消息。

## 离线消息机制

### 核心规则

- 返回当前用户可见会话的时间线增量（双向：user ↔ assistant）。
- 离线拉取仅返回聊天时间线消息（TEXT + CHAT_INFO）。
- 新客户端首次创建游标时起点为当前时间。

### 客户端标识

- 客户端生成稳定 UUID（设备/安装级），作为 device_id。
- device_id 必须随离线拉取与 ACK 上送，服务端按 (user_id, device_id) 区分游标。
- device_id 生成与持久化规范见：`../client/base/device-id.md`。

### 游标模型

- 存储在 `message_devices`。
- 使用二元游标：`last_acked_msg_sent_at` + `last_acked_msg_id`。
- 游标仅在收到 ACK 后推进。

### 处理流程

1. 客户端断线重连后优先请求离线消息（带 device_id）。
2. 服务端使用 `message_devices.last_acked_msg_*` 作为起点，拉取未确认消息并返回。
3. 客户端成功落盘后发送 ACK（可在补偿完成后统一 ACK）。
4. 服务端更新游标。

### ACK 要求

- 实时消息与离线消息都必须 ACK。
- ACK 只能在离线补偿完成后发送，避免游标越过未补偿消息。
- 实时消息在补偿完成前不得 ACK，应先落盘并进入待 ACK 队列。
- ACK 游标必须基于客户端已持久化的最大 (sent_time_ms, msg_id_server)。
- 未 ACK 的消息会在后续拉取中重复返回，避免消息丢失。
- 服务端仅接受连续递进的 ACK；小于当前游标的 ACK 会被忽略并记录 warning。
- 服务端以 `msg_id_server` 对应消息的 `sent_at`（对外等价字段名为 `sent_time_ms`）为准推进游标。

### 接口契约

- 接口路径、请求/响应字段与分页参数见：`../../api/messages-offline.md`。
