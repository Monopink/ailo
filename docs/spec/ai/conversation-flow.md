# 对话流程

本文档只记录对话编排规则、决策条件和失败边界，不重复子系统实现细节与字段字典。

## 职责边界

- 端到端编排：本文档
- 错误处理与降级：[`../error-handling.md`](../error-handling.md)
- 缓冲与计时：[`../message/buffer.md`](../message/buffer.md)
- Prompt 构建：[`prompt-building.md`](prompt-building.md)
- LLM 调用与响应字段：[`llm-interaction.md`](llm-interaction.md)
- 关系计算：[`relationship-system.md`](relationship-system.md)
- 业务告警：[`../alerting.md`](../alerting.md)
- 消息发送：[`message-sending.md`](message-sending.md)
- Provider 传递：[`../message/leancloud.md`](../message/leancloud.md)、[`../message/websocket.md`](../message/websocket.md)
- 失败投递：[`../message/failure-handling.md`](../message/failure-handling.md)

## 主流程

```
用户消息入站
  -> 入站验证与安全检测
  -> 写入 ai_conversation_items
  -> 缓冲聚合 + 计时
  -> 锁定窗口（可抢占）
  -> 构建 Prompt
  -> 调用 LLM + L0/L1 校验（含重试）
  -> 响应处理
  -> 消息发送（可选）
  -> 会话副作用（可选）
  -> Provider 投递
```

## 阶段规则

### 阶段 1：消息接收

- 入口为统一入站消息事件（由 Provider 适配产生），支持 LeanCloud Webhook 与 WebSocket。
- 必须完成 token 校验、消息格式校验、解密（如启用）。
- 验证失败必须终止流程，消息不得进入上下文与缓冲。

详见：[`../message/leancloud.md`](../message/leancloud.md)、[`../message/websocket.md`](../message/websocket.md)

### 阶段 2：安全检测

- 必须执行频率限制、内容安全、用户状态校验。
- 任一检测失败，终止流程并拒绝本条消息。
- 安全检测失败不允许继续进入 LLM 链路。

### 阶段 3：写入上下文事实

- 入站用户消息必须落库到 `ai_conversation_items`。
- `text` 类型必须包含 `text_content`；攻击排除标记初始值为 `0`。
- 写入失败必须终止，不允许创建新的处理窗口。

详见：[`../message/context.md`](../message/context.md)

### 阶段 4：缓冲聚合与计时

- 同会话存在活跃窗口（`WAITING_WAKEUP` 或 `OPEN`）时必须合并，不存在时创建新窗口。
- 是否进入唤醒等待由 `wake_window_ms` 决定；唤醒等待与 timer 等待采用串行叠加语义，统一体现在 `buffer_expires_at_ms` 的计算中。
- `typing_start/typing_end` 在 `WAITING_WAKEUP` 与 `OPEN` 都必须更新计时。
- 统一以 `buffer_expires_at_ms` 判定是否到期进入处理。

详见：[`../message/buffer.md`](../message/buffer.md)

### 阶段 5：锁定与抢占

- 同会话同一时刻最多允许一个 LOCKED 窗口。
- 新窗口到期可抢占旧 LOCKED 窗口。
- 锁定候选来自已到期窗口（`WAITING_WAKEUP` 或 `OPEN`）。
- LOCKED/COMPLETE/CANCELLED 转换使用条件更新（CAS）。
- 抢占生效点为新窗口锁定并推进 `active_turn_version`。
- 旧代次在检测到 `active_turn_version` 切换后必须立即中止并丢弃当前结果。
- 抢占是并发正常路径，不按业务失败处理。

详见：[`../message/buffer.md`](../message/buffer.md#到期扫描与锁定)

### 阶段 6：Prompt 构建

- 必须按模板占位符规则构建完整 `messages`。
- `AIInstance`、`AIStyle`、`AIPersonality` 缺失属于硬错误，必须终止。
- `Profile` 缺失允许降级：`self_profile` 置空并继续。
- `ai_conversation_context_max_messages`、`ai_conversation_context_time_window_days` 缺失或非法时，本轮对话处理必须静默失败并结束 buffer。
- 配置类静默失败必须记录错误日志、审计日志，并触发告警。

详见：[`prompt-building.md`](prompt-building.md)

### 阶段 7：LLM 调用与校验闸门

- 按配置选择流式或非流式调用。
- 流式与非流式都必须执行抢占校验。
- attempt 循环仅覆盖 LLM 调用、解析、L0/L1 校验与 attempt 落库；阶段 3-6 不随重试重复执行。
- 调用失败、超时、JSON 解析失败、L0 失败会触发重试；达到上限后按静默失败收敛。
- 重试使用固定间隔 backoff；相关配置缺失或类型错误按 fail-fast 处理并终止当前 turn。
- L1 字段校验失败仅丢弃对应字段整项，不阻断消息发送。
- 每个 attempt 必须写入 `ai_request_logs`，失败 attempt 也必须可审计。

详见：[`llm-interaction.md`](llm-interaction.md)

### 阶段 8：响应处理

- 安全副作用始终生效：`attack_detected -> should_block`。
- `attack_detected=true` 时执行上下文排除、审计落库与风险统计更新；三者为 best-effort，失败记录 ERROR，不终止消息流程。
- `should_block` 状态更新失败时终止发送路径。
- `should_reply=false` 时不得发送 `outgoing_messages` 与 `followup_messages`。
- `should_reply=false` 时会话副作用可继续执行，但必须先通过抢占校验。

详见：[`llm-interaction.md`](llm-interaction.md#处理顺序)

### 阶段 9：消息发送与投递（可选）

- `should_reply=true` 时，按顺序发送 `outgoing_messages`，再按延迟发送 `followup_messages`。
- 发送过程中仅 `CONTENT_INPUT` 可触发抢占流程。
- 新窗口锁定并切换 `active_turn_version` 后，中断旧代次未完成发送。
- typing 事件不触发发送中断。
- Provider 投递失败走统一失败处理链路，不改变消息事实定义。

详见：[`message-sending.md`](message-sending.md)、[`../message/failure-handling.md`](../message/failure-handling.md)

### 阶段 10：会话副作用（可选）

- `memory_operations`、`score` 为会话副作用，独立执行并独立提交。
- `should_reply=true` 时，会话副作用受首条发送门槛控制。
- `should_reply=false` 时，不受首条发送门槛控制，但执行前必须再次通过抢占校验。
- `memory_operations` 写入统一走 `memory_policy_service`，并在写入链路内完成 `recent` 归档治理。
- 会话副作用中的记忆检索阶段保持只读，不在检索阶段修改记忆状态。
- 仅在响应包含合法 `score` 时执行关系计算。
- 单项副作用失败仅结束该项副作用处理并记录日志。
- 会话副作用链路允许产生业务告警事件（best-effort，见 [`../alerting.md`](../alerting.md)），失败仅记录 ERROR，不影响消息发送与其他副作用提交。

详见：[`llm-interaction.md`](llm-interaction.md#处理顺序)、[`relationship-system.md`](relationship-system.md)

## 全局失败边界

- 任何入站校验失败：终止于入站层，不进入对话编排。
- 任何安全检测失败：终止于安全层，不进入 LLM 链路。
- 任何抢占事件：在 `active_turn_version` 切换后立即中止旧处理，旧结果必须丢弃。
- 任何 L0 校验失败：进入重试；达到上限后静默失败并 finalize buffer 为 `COMPLETE`。
- 配置类异常：静默结束本轮处理，不向用户返回错误提示；必须记录错误日志、审计日志并触发告警。
- 非配置类异常：按系统故障路径处理并触发告警，不归类为配置异常。
- 任何 L1 校验失败：仅跳过对应副作用字段，不阻断消息发送。
- 任何 style/personality 配置契约不匹配：必须报错并终止处理。
- 首条发送门槛未达成且发生抢占：不得推进会话副作用。
- 任何发送/投递失败：按消息失败处理规则推进，不在本文件重复定义重试实现。
