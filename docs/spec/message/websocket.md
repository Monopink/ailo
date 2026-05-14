# WebSocket Provider

本文档定义 WebSocket 作为消息传输层（Provider）的协议与约束。

定位：

- WebSocket 只负责传输与路由（transport only），不承载业务逻辑
- 所有业务处理复用统一消息管线：验证/解密 → buffer → context → LLM → 响应处理 → 发送

分层职责：

- Provider：入站 payload 适配、按 endpoint 投递语义
- Transport：连接管理、状态维护、发送队列
- API 接入：握手鉴权、帧级协议处理、调用统一业务入口

---

## 端点

- WebSocket：`GET /ws/messages`

---

## 鉴权

- 所有业务鉴权使用 JWT。
- HTTP API 使用 `Authorization: Bearer <token>`。
- 浏览器 WebSocket 无法自定义 `Authorization` Header，因此客户端先通过 `POST /api/v1/messages/ws-session` 获取短时 `ws_ticket`，再使用首帧 `auth` 提交 `ws_ticket` 与 `device_id`。

---

## 路由粒度：endpoint（客户端标识 device_id）

- 客户端必须提供稳定 `device_id`（UUID，设备/安装级）。
- WebSocket 连接建立并完成 `auth` 后，服务端按 (user_id, device_id) upsert Presence endpoint（`message_endpoints`）并得到 `endpoint_id`。
- WebSocket endpoint 属于 DEVICE 粒度（`endpoint_scope=DEVICE`，`target_key=device_id`）。
- 服务端在 endpoint 上记录连接归属实例（`owner_instance_id`）与归属租约（`owner_lease_expires_at`），并在 `auth/ping` 续租。
- **服务端内部路由/投递目标以 `endpoint_id` 为准**（或至少以 (user_id, device_id) 为路由键）；禁止仅用 `device_id` 作为内部路由键，避免多账号复用同一 device_id 时串线。

Presence endpoint 的活跃状态由 lease 管理（见下文“Lease”）。

---

## Lease（活跃 TTL）

系统使用两类 lease：

1) Presence lease（短）

- 用于 WebSocket 在线活跃
- 由 `ping` 或服务端内部心跳续租

固定值：

- TTL：90 秒（协议固定值）

## 幂等与去重

- 幂等键与幂等行为见：`../../api/websocket-messages.md`。
- 消息 ID 语义与用法见：`schema.md`。

---

## WS 帧级 ACK 与 HTTP 投递 ACK

WS 的 `ack` 语义：

- 表示“服务端已接收该 WS 帧并完成校验/入队”
- 不表示“消息已投递/已读”
- 对于 `send_message`，`ack.payload` 返回字段见：`../../api/websocket-messages.md`。

投递确认使用 HTTP ACK：

- `POST /api/v1/messages/ack`

离线补偿使用：

- `GET /api/v1/messages/offline`

---

## 多端在线同步（Timeline Fanout）

当消息落库到 `message_history` 后，服务端应将该消息作为 `event: message` 推送给该用户的所有活跃 endpoints（lease 未过期），用于多设备在线同步。

- 广播范围仅限当前用户（user_id 维度）的活跃 endpoints；不得跨 user 广播，避免串线。
- 广播应包含“用户自己发送消息”的回显（用于多端同步与拿到 `msg_id_server` 的统一路径）。
- 业务层按 endpoint 的 `provider` 执行 fanout；仅当目标 endpoint.provider=WebSocket 时，通过本通道推送 `event: message`。
- WS 推送允许重复（at-least-once）；客户端按 `msg_id_server` 去重。

---

## 协议与消息类型

协议细节（API 视角）见：`docs/api/websocket-messages.md`。

补充约束：

- 入站业务定位键统一使用 `conversation_id`（等于 `contacts.conversation_id`），Provider 仅负责传输与鉴权；业务层按 `conversation_id` 查找 contact/instance 并进入统一消息管线。
- 客户端可上送 `typing`（start/end）以驱动 buffer 的双计时器策略与真实聊天节奏。

---

## 会话地址与域名故障恢复

- `POST /api/v1/messages/ws-session` 返回的 `session.server_url` 仅来自 `system_configs.api_base_url`，不允许回退到请求 Host。
- `api_base_url` 校验规则：
  - `prod` 环境仅允许 `https://` 绝对地址；
  - 非 `prod` 环境仅允许回环地址（`localhost`、`127.0.0.1`、`::1`）使用 `http://`，其余地址必须使用 `https://`。
- 客户端命中 `createSocketTask:fail url not in domain list` 时，统一归类为 `WS_DOMAIN_NOT_ALLOWED`。
- 客户端进入 `config_error` 后执行固定恢复流程：
  - 立即强制刷新一次会话配置并重连；
  - 若仍失败，停止高频指数退避重连；
  - 进入低频自动探测（`60s` 周期，`±10%` 抖动）；
  - 探测成功后恢复到正常连接状态机。
- `config_error` 状态下发送路径返回确定性错误 `WS_DOMAIN_NOT_ALLOWED`，用于失败态展示与运行态事件聚合。
