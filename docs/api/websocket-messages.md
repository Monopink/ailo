# WebSocket 消息通道

本文档定义通用 WebSocket 消息通道（transport only）的 API 视角协议，用于实时收发消息与事件。

---

## 端点

- **路径**：`GET /ws/messages`
- **协议**：WebSocket

---

## 鉴权

WebSocket 连接建立后，客户端必须先发送 `auth` 消息完成鉴权。

原因：浏览器 WebSocket API 无法自定义 `Authorization` Header；因此客户端先通过 `POST /api/v1/messages/ws-session` 获取短时 `ws_ticket`，再在首帧 `auth` 提交票据。

约束：所有客户端（浏览器/非浏览器）均使用首帧 `auth` 消息鉴权；不使用/不依赖握手 `Authorization` Header。

会话票据接口见：`messages-ws-session.md`。

---

## 公共消息格式（JSON）

```json
{
  "type": "auth | ping | send_message | typing | ack | event | error",
  "ws_frame_id": "random_string",
  "payload": {}
}
```

- `type`：消息类型
- `ws_frame_id`：WS 帧级请求 ID；客户端请求由客户端生成（推荐短随机串，例如 Base64URL 22~26 位），服务端推送事件由服务端生成
- `payload`：负载

说明：

- WS 的 `ack` 仅表示“服务端已接收该 WS 帧并完成校验/入队”，不表示“消息已投递/已读”。
- `ack` 仅由服务端返回；客户端不会发送 `ack` 类型消息。
- 投递确认使用 HTTP ACK：`POST /api/v1/messages/ack`（见 `messages-offline.md`）。
- 对于 `send_message`/`typing` 等入站帧，服务端可在 `ack.payload` 中返回与该帧相关的服务端生成字段（例如 `msg_id_server`），用于客户端对齐与后续 HTTP ACK 推游标。

---

## 消息类型

### auth（客户端 → 服务端）

```json
{
  "type": "auth",
  "ws_frame_id": "R0k5x0V6pL3h9Jk8m2Q7eQ",
  "payload": {
    "ws_ticket": "<ws_session_ticket>",
    "device_id": "uuid"
  }
}
```

约束：

- `device_id` 必须是稳定 UUID（设备/安装级）；生成与持久化规范见 `../spec/client/base/device-id.md`。
- `ws_ticket` 必须来自 `POST /api/v1/messages/ws-session`，并且处于有效期内。
- 服务端会按 (user_id, device_id) 注册 Presence endpoint 并续租。

成功响应：

```json
{
  "type": "ack",
  "ws_frame_id": "R0k5x0V6pL3h9Jk8m2Q7eQ",
  "payload": { "ok": true }
}
```

失败响应：返回 `error` 并关闭连接。

安全拒绝补充：

- 服务端会在 `auth` 帧执行 IP 封禁检查与攻击签名检测。
- 命中时返回 `type=error`，随后关闭连接（close code `1008`）。
- 用户侧文案保持通用拒绝语义，不暴露具体命中规则。

---

### ping（客户端 → 服务端）

用于保活与续租 Presence lease。

```json
{
  "type": "ping",
  "ws_frame_id": "mA3p9Lq2cV8t1Hn7sK0dWQ",
  "payload": {}
}
```

成功响应：`ack`。

---

### send_message（客户端 → 服务端）

发送用户消息，进入统一消息管线（验证/解密 → buffer → LLM → 发送）。

```json
{
  "type": "send_message",
  "ws_frame_id": "Qp8n2sT4vK1c0Xy6hJ3rZw",
  "payload": {
    "msg_id_client": "client_1710001111222_abc123",
    "conversation_id": "conv_xyz789",
    "content": "你好",
    "supports_typing": true,
    "client_sent_time_ms": 1710001111222
  }
}
```

约束：

- `msg_id_client` 必填，用于幂等去重。
- `conversation_id` 必填（等于 `contacts.conversation_id`），作为入站业务定位键；服务端通过该值查找 contact/instance 并进入统一消息管线。
- `client_sent_time_ms` 可选；时间字段命名规范见 `../spec/time-format.md`。
- `msg_id_server` / `msg_id_client` 的语义与用法见 `../spec/message/schema.md`。

成功响应：

```json
{
  "type": "ack",
  "ws_frame_id": "Qp8n2sT4vK1c0Xy6hJ3rZw",
  "payload": {
    "ok": true,
    "msg_id_server": "msg_223788765171155999",
    "sent_time_ms": 1710001111333
  }
}
```

---

### typing（客户端 → 服务端）

用于上送输入状态（开始/结束），进入统一消息管线并驱动 buffer 计时器策略。

```json
{
  "type": "typing",
  "ws_frame_id": "n8A2sQp0cV7t1Hn7sK0dWQ",
  "payload": {
    "msg_id_client": "client_1710001111333_def456",
    "conversation_id": "conv_xyz789",
    "typing_state": "start | end",
    "supports_typing": true,
    "client_sent_time_ms": 1710001111333
  }
}
```

说明：

- `typing` 是实时输入状态事件，服务端可用于驱动 buffer 策略与推送给对端。
- `typing` 上报必须包含 `conversation_id` 与 `typing_state`；身份信息由服务端基于鉴权身份 + `conversation_id` 推导。
- `typing_state=start/end` 会在服务端分别映射为内部消息类型 `TYPING_START (2)` / `TYPING_END (3)`（见 `../spec/message/schema.md` 与 `../spec/message/special-types.md`）。
- `typing` 不写入 `message_history`（仅用于实时与 buffer 策略）。
- `typing` 不等同于“发送消息”，也不承载投递确认；投递确认仍使用 HTTP ACK。
- 若客户端额外携带 `from_qiao_id/to_qiao_id`，服务端应忽略该字段，防止客户端伪造身份。
- 服务端不强制发送 `typing_state=end`；客户端应在收到 TEXT 消息或超时后自行隐藏输入态。
- 客户端发送与展示统一规则见 `../spec/message/typing.md`（含 `typing_start` 1 秒 buffer）。

成功响应：`ack`。

---

### event（服务端 → 客户端）

服务端推送事件，用于“即时收取消息”与“真实聊天节奏”。

事件集合（最小）：

- `message`：新消息（user/assistant/chat_info/notification）
- `typing`：输入状态变化

说明：

- 多端在线同步：服务端会将时间线消息广播到该用户的所有活跃 endpoints（包含“用户自己发送消息”的回显）。
- WS 推送允许重复（at-least-once）；客户端按 `msg_id_server` 去重。
- 广播范围仅限当前登录用户的活跃 endpoints；不得跨 user 广播。
- `msg_id_client` 是 `event: message` 的可选回传字段：用户源消息可回传原 `msg_id_client`；assistant/系统消息通常为 `null` 或省略。

#### event: message

用户自发消息回显示例：

```json
{
  "type": "event",
  "ws_frame_id": "tJ6b0Vx3nQ2p8aZ5cL9sHw",
  "payload": {
    "event_type": "message",
    "message": {
      "msg_id_server": "msg_223788765171155999",
      "msg_id_client": "client_1710001111222_abc123",
      "conversation_id": "conv_272638151019859968",
      "from_qiao_id": "qiao_user001",
      "to_qiao_id": "qiao_xm001",
      "message_type": 1,
      "content": "你好",
      "client_sent_time_ms": 1710001111222,
      "sent_time_ms": 1710001111333,
      "metadata": {}
    }
  }
}
```

assistant/系统消息示例：

```json
{
  "type": "event",
  "ws_frame_id": "tJ6b0Vx3nQ2p8aZ5cL9sHw",
  "payload": {
    "event_type": "message",
    "message": {
      "msg_id_server": "msg_223788765171155999",
      "msg_id_client": null,
      "conversation_id": "conv_272638151019859968",
      "from_qiao_id": "qiao_xm001",
      "to_qiao_id": "qiao_user001",
      "message_type": 1,
      "content": "我在呢。",
      "client_sent_time_ms": null,
      "sent_time_ms": 1710002222333,
      "metadata": {}
    }
  }
}
```

说明：

- 时间字段命名规范见 `../spec/time-format.md`。

#### event: typing

```json
{
  "type": "event",
  "ws_frame_id": "bC1m7nR4xT0q9sK2vP5dYw",
  "payload": {
    "event_type": "typing",
    "typing": {
      "conversation_id": "conv_xyz789",
      "from_qiao_id": "qiao_xm001",
      "to_qiao_id": "qiao_user001",
      "typing_state": "start | end",
      "time_ms": 1710002222000
    }
  }
}
```

### error（服务端 → 客户端）

```json
{
  "type": "error",
  "ws_frame_id": "zX4q1sN8cM2p7vT0hL6aBw",
  "payload": {
    "error_code": 24032001,
    "message": "需要先登录",
    "request_id": "req_20260218_abc123"
  }
}
```

约束：

- `error_code` 使用 8 位数字（`SSMMEEEE`），`/ws/messages` 固定 `SS=24`、`MM=03`。
- `message` 对用户可读；仅 5xx 场景使用统一文案：`系统错误（error_code）`。
- `request_id` 用于日志追踪。

---

## 幂等与去重

- `send_message` 的幂等键：`(conversation_id, msg_id_client)`。
- 重复发送相同 `msg_id_client` 时，服务端必须幂等处理并返回 `ack`。
- 幂等重发时，`ack.payload.msg_id_server` 必须保持一致。
