# 对话流程

本文档只记录对话编排规则、决策条件和失败边界，不重复子系统实现细节与字段字典。

## 职责边界

- 端到端编排：本文档
- 缓冲与计时：[`../message/buffer.md`](../message/buffer.md)
- Prompt 构建：[`prompt-building.md`](prompt-building.md)
- LLM 调用与响应字段：[`llm-interaction.md`](llm-interaction.md)
- 关系计算：[`relationship-system.md`](relationship-system.md)
- 消息发送：[`message-sending.md`](message-sending.md)
- Provider 传递：[`../message/leancloud.md`](../message/leancloud.md)
- 失败投递：[`../message/failure-handling.md`](../message/failure-handling.md)

## 主流程

```
用户消息入站
  -> 入站验证与安全检测
  -> 写入 ai_conversation_items
  -> 缓冲聚合 + 计时
  -> 锁定窗口（可抢占）
  -> 构建 Prompt
  -> 调用 LLM + Schema 校验
  -> 响应处理
  -> 消息发送（可选）
  -> 会话副作用（可选）
  -> Provider 投递
```

## 阶段规则

### 阶段 1：消息接收

- 入口固定为 LeanCloud Webhook。
- 必须完成 token 校验、消息格式校验、解密（如启用）。
- 验证失败必须终止流程，消息不得进入上下文与缓冲。

详见：[`../message/leancloud.md`](../message/leancloud.md)

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
- 是否进入唤醒等待由 `wake_window_ms` 决定，唤醒作为计时门控参与统一截止时间计算。
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

详见：[`prompt-building.md`](prompt-building.md)

### 阶段 7：LLM 调用与校验闸门

- 按配置选择流式或非流式调用。
- 流式与非流式都必须执行抢占校验。
- 仅 Schema 校验通过的响应允许进入后续处理。
- 调用失败、超时、Schema 失败均不得写入业务更新结果。

详见：[`llm-interaction.md`](llm-interaction.md)

### 阶段 8：响应处理

- 安全副作用始终生效：`attack_detected -> should_block`。
- 安全副作用失败时终止发送路径。
- `attack_detected=true` 时必须标记本轮用户消息为上下文排除。
- `should_reply=false` 时不得发送 `outgoing_messages` 与 `followup_messages`。

详见：[`llm-interaction.md`](llm-interaction.md#处理顺序)

### 阶段 9：消息发送与投递（可选）

- `should_reply=true` 时，按顺序发送 `outgoing_messages`，再按延迟发送 `followup_messages`。
- 发送过程中仅 `CONTENT_INPUT` 可触发抢占流程。
- 新窗口锁定并切换 `active_turn_version` 后，中断旧代次未完成发送。
- typing 事件不触发发送中断。
- Provider 投递失败走统一失败处理链路，不改变消息事实定义。

详见：[`message-sending.md`](message-sending.md)、[`../message/failure-handling.md`](../message/failure-handling.md)

### 阶段 10：会话副作用（可选）

- 会话副作用受首条发送门槛控制：`memory_operations`、`score`。
- 仅在响应包含 `score` 时执行关系计算。
- `memory_operations` 与 `score` 独立执行并独立提交。
- 单项副作用失败仅结束该项副作用处理并记录日志。

详见：[`llm-interaction.md`](llm-interaction.md#处理顺序)、[`relationship-system.md`](relationship-system.md)

## 全局失败边界

- 任何入站校验失败：终止于入站层，不进入对话编排。
- 任何安全检测失败：终止于安全层，不进入 LLM 链路。
- 任何抢占事件：在 `active_turn_version` 切换后立即中止旧处理，旧结果必须丢弃。
- 任何 LLM 校验闸门失败：不得推进关系更新与消息发送。
- 任何 style/personality 契约不匹配或 score range 不合规：必须报错并终止处理。
- 首条发送门槛未达成且发生抢占：不得推进会话副作用。
- 任何发送/投递失败：按消息失败处理规则推进，不在本文件重复定义重试实现。
