# Typing 输入状态约定

本规范定义所有客户端（Web/小程序/APP）在 `typing` 上报与展示上的统一行为，避免各端实现分叉。

---

## 协议范围

- `typing` 为跨 Provider 的统一语义事件，传输层编码由 Provider 决定。
- 客户端上报（统一语义）：`typing_start` / `typing_end`
- 服务端下发（统一语义）：`typing_start` / `typing_end`
- 上报字段要求：
  - 必须携带 `conversation_id`
  - 必须携带开始/结束状态（WS 为 `typing_state`；LeanCloud 为 `message_type=2/3`）
  - `from_qiao_id/to_qiao_id` 由服务端按鉴权身份与会话关系推导
- 相关协议字段定义见：
  - `docs/api/websocket-messages.md`
  - `docs/spec/message/schema.md`
  - `docs/spec/message/special-types.md`

---

## 客户端发送规则（上报 typing）

### Provider 编码

- WebSocket：发送 `type=typing` 帧，字段 `typing_state=start|end`
- LeanCloud：发送 TypedMessage，字段 `message_type=2|3`（TYPING_START / TYPING_END），并以 `transient=true` 发送

### typing_start（带 1 秒 buffer）

必须同时满足：

1. 当前会话可发送（已鉴权、会话已选中）
2. 输入从“空”变为“有内容”，**或**在“空内容”状态进入输入法组合（composition）
3. 客户端灵活性补偿：输入框 focus 时已存在非空内容（例如失焦后回到输入框继续输入）

发送约束：

- `typing_start` 必须经过 **1 秒 buffer（防抖）** 后再发送
- 1 秒内若输入重新变空，必须取消本次 `typing_start`
- 同一会话在已处于 typing active 时，禁止重复发送 `typing_start`
- 补偿场景（focus + 非空）允许发送 `typing_start`，但仍必须遵守上述 buffer 与去重约束

### typing_end（立即发送）

触发条件（任一满足即发送）：

- 输入内容变空，且输入法组合已结束
- 输入框失焦（blur）
- 会话切换 / 账号切换
- 连接断开或进入不可发送状态

发送约束：

- `typing_end` **不做 buffer，不延迟**
- 若当前未处于 typing active，可不发送 `typing_end`（避免无效帧）
- 用户发送消息时：仅清理本端 typing 状态，**不发送 `typing_end`**

---

## 客户端展示规则（显示对方 typing）

- 只展示“对方正在输入”，不展示自己 typing
- 判定必须同时满足：
  - `conversation_id` 等于当前会话
  - `from_qiao_id/to_qiao_id` 与当前自己/对方身份严格匹配

隐藏规则：

- 收到对方 `typing_end`：立即隐藏
- 收到当前会话的对方 TEXT：立即隐藏
- 本端发送消息：立即隐藏
- 兜底超时：最多显示 30 秒，超时自动隐藏

---

## 服务端行为约束（客户端不可假设）

- `typing_start/typing_end` 为 realtime best-effort 事件
- 服务端按活跃 endpoint 的 `provider` 扇出 typing
- WebSocket endpoint：下发 `event_type=typing`
- LeanCloud endpoint：下发 `message_type=2|3`，并以 `transient=true` 发送
- typing 扇出异常仅记录日志，不中断 timeline 消息发送流程
- 服务端不保证一定下发 `typing_end`
- 客户端必须依赖“对方 TEXT + 30 秒超时”完成兜底收敛

---

## 实施要求

- 所有客户端必须遵守本规范，不允许各端自定义 typing 语义
- 管理端 Chat Console 与业务客户端使用同一套 typing 规则
