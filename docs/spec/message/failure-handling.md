# 消息投递失败处理

本文档说明消息投递失败的处理策略与自动重试调度实现。
投递维度以 endpoint 为单位，`message_deliveries` 记录每个 endpoint 的投递结果，`message_dispatch_outbox` 负责重试调度。

恢复入口约束：

- timeline 发送恢复入口统一为 `message_dispatch_outbox`
- 当 `should_reply=true` 且存在 assistant 文本发送时，buffer 进入 `COMPLETE` 前，首条 assistant 文本必须已写入 `message_dispatch_outbox`

## 失败场景分类

### Provider 层面失败

- 网络错误（超时、连接失败）→ 进入 outbox 自动重试
- Provider 服务异常（服务不可用、限流）→ 进入 outbox 自动重试
- 消息格式错误（payload 不正确）→ 记录日志，不重试

### 业务层面失败（拒收）

- 用户被屏蔽（contacts.is_blocked = 1）→ 发送 CHAT_INFO，不重试
- AI 屏蔽用户（ai_instances.status = 3）→ 发送 CHAT_INFO，不重试
- 用户不是好友（contacts 表无记录）→ 发送 CHAT_INFO，不重试
- 拒收分支返回 `business_rejected` 业务结果，不抛异常中断主流程

详见 [special-types.md](special-types.md#block-功能和消息拒收)

---

## 数据模型：message_dispatch_outbox + message_deliveries

完整表结构见 [data-dict/message.md](../../data-dict/message.md)。

说明：

- 消息内容来源于 `message_history`（按 `msg_id_server` 查询），`message_deliveries` 不重复存储消息内容。
- Outbox 负责调度与重试；`message_deliveries` 不承担调度职责。
- `message_dispatch_outbox` 不可缺失于 timeline 发送链路。
- 语义约定：
  - `dispatched` 表示服务端已成功调用 provider 投递（WebSocket 场景为服务端成功写入连接）；不代表客户端已收到/已 HTTP ACK。
  - `pending` 仅用于需要异步回执/回调才能确认投递结果的 provider。

---

## 投递记录写入

### 写入时机

一次出站消息会投递到一个或多个活跃 endpoints：

1. 创建出站消息事实：写入 `message_history`
2. 写入 `message_dispatch_outbox`（同事务提交）
3. Worker 读取 outbox，计算目标 endpoints
4. 调用 provider sender 发送（WebSocket sender / LeanCloud sender），并写/更新 `message_deliveries`
5. 根据执行结果更新 outbox 状态（done 或 pending/failed）

对于首条 assistant 文本：

1. `message_history`、`message_dispatch_outbox`、`ai_conversation_items` 同事务写入
2. `finalize_buffer_if_locked(... -> COMPLETE)` 在同一事务内执行

### 状态更新规则

- 发送成功：`status = dispatched`，写入 `dispatched_at`，必要时写入 `provider_msg_id`
- 发送失败：`status = failed`，写入失败原因

说明：

- WebSocket 等可同步判定投递结果的 provider，可在发送成功后直接写入 `dispatched`（无需长期停留在 `pending`）。

---

## 重试机制

目标：

- 对“可重试”的 provider 失败进行自动调度重试，避免瞬态网络问题导致消息永久失败。

调度来源：

- 重试调度基于 `message_dispatch_outbox`，不是基于 `message_deliveries` 扫描。

指数退避策略：

- 首次派发：任务进入 worker 后立即执行
- 第 1 次重试：1 分钟后
- 第 2 次重试：5 分钟后
- 第 3 次重试：15 分钟后
- 超过 3 次重试后标记 `failed`

计数语义：

- `attempt_count` 仅统计“重试次数”，不包含首次派发。

重试流程：

1. 定期扫描待重试投递：
   - `status = pending`
   - `next_retry_at <= now`
   - `attempt_count` 未超过上限
2. 查询 `message_history` 获取消息内容与元数据
3. 再次调用 provider 投递
4. 更新 outbox：
   - 成功：`done`
   - 失败可重试：递增 `attempt_count`，重算 `next_retry_at`，回到 `pending`
   - 失败不可重试/超过上限：`failed`
5. 同步写入/更新 `message_deliveries`（endpoint 结果）

---

## Realtime Typing 失败语义

- `typing_start/typing_end` 为 realtime best-effort 事件
- typing 失败只记录日志，不写 outbox，不触发 timeline 失败
