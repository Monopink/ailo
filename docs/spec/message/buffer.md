# AI 消息缓冲机制

本文档说明 AI 如何聚合用户消息、何时触发处理。

- 可抢占：新消息到期后直接覆盖旧处理，不被旧请求阻塞
- 幂等：结果落地前二次校验，旧请求结果丢弃
- 职责分离：buffer 管理状态，conversation_items 存储内容

## 架构设计

### 表结构分离

系统使用两个表实现职责分离：

**ai_message_buffer**：纯粹的消息聚合状态机

- 管理双计时器（micro/macro）
- 管理唤醒门控（wake）
- 追踪窗口元数据（first/last msg_id, message_count）
- 控制状态转换（WAITING_WAKEUP / OPEN → LOCKED → COMPLETE/CANCELLED）
- **不存储消息内容**

**ai_conversation_items**：对话历史存储

- 存储扁平字段消息（message_type/text_content/media_url/media_metadata）
- 支持多模态内容（文本、图片、音频等）
- 提供上下文查询和审计功能
- 标记攻击消息（is_excluded_from_context）

详见 [context.md](context.md)

### ai_message_buffer 核心字段

涉及数据表：`ai_message_buffer`

### 约束与索引

- 同会话唯一锁：`UNIQUE(user_qiao_id, instance_qiao_id) WHERE aggregate_state=2`
- 到期扫描索引：`idx_ai_message_buffer_expire_scan`（`aggregate_state IN (0,1)`）
- 时间基准：统一使用数据库时钟 `(EXTRACT(EPOCH FROM NOW())*1000)::BIGINT`

## 双计时器机制

### 设计原理

使用微计时器和宏计时器平衡响应速度与消息聚合：

- 微计时器 - 每条新消息重置，快速响应 - 默认 3-16秒
- 宏计时器 - 从 typing_start 开始计时，防止无限等待 - 默认 32秒上限

`buffer_expires_at_ms` 是唯一调度截止时间，计算规则为：

1. `timer_due_ms = min(micro_expires_at_ms, macro_expires_at_ms)`（忽略 NULL）
2. 若不存在 `wake_delay_ms`，则 `buffer_expires_at_ms = timer_due_ms`
3. 若存在 `wake_delay_ms` 且存在 `timer_due_ms`，则：
   - `buffer_expires_at_ms = timer_due_ms + wake_delay_ms`
4. 若存在 `wake_delay_ms` 但 `timer_due_ms` 为 NULL，则 `buffer_expires_at_ms = now_ms + wake_delay_ms`

说明：

- Wake 与 timer 的语义为**串行叠加**：先等待 timer 到期，再等待 wake 剩余时间。
- `wake_delay_ms` 的时间基准为 `now_ms`（优先 DB 时钟），并且是“串行追加延迟”而非绝对到期时间戳。

### 消息类型与等待时间

从 system_configs 表获取配置：

- content_typing - message_buffer_normal_wait_ms - 默认 3000ms
- content_no_typing - message_buffer_no_typing_wait_ms - 默认 8000ms
- typing_start.short - message_buffer_typing_short_wait_ms - 默认 16000ms
- typing_start.total - message_buffer_typing_total_wait_ms - 默认 32000ms
- typing_end - message_buffer_typing_end_wait_ms - 默认 3000ms

### 状态转换规则

#### 无上一条消息（last_message_category = NULL）

- content_typing → 设置微计时器（message_buffer_normal_wait_ms）
- content_no_typing → 设置微计时器（message_buffer_no_typing_wait_ms）

#### 上一条为 content_typing

- content_typing → 设置微计时器
- typing_start → 设置微计时器（typing_short_wait_ms）并设置宏计时器（typing_total_wait_ms）

#### 上一条为 typing_start

- content_typing → 取消宏计时器，设置微计时器
- typing_end → 设置微计时器（message_buffer_typing_end_wait_ms）

#### 上一条为 typing_end

- content_typing → 设置微计时器
- typing_start → 设置微计时器（typing_short_wait_ms）

#### 上一条为 content_no_typing

- content_no_typing → 设置微计时器

#### 其他情况组合

不影响计时器且不记录为上一条消息。

约束：

- typing 事件只影响计时，不触发发送中断。
- typing 事件在 `WAITING_WAKEUP` 与 `OPEN` 状态都必须生效，不允许被状态分支忽略。
- 内容型输入（TEXT/IMAGE/AUDIO 等）到达时触发入站代次推进（`ingress_version`）。
- 抢占在“新窗口到期并锁定”时生效（推进 `active_turn_version`）。

## 唤醒机制（Wake Mechanism）

### 设计目标

模拟真人"看到消息后思考一段时间"的行为，使 AI 响应速度反映与用户的关系等级。

### 状态扩展

在原有状态基础上新增 WAITING_WAKEUP 状态：

- WAITING_WAKEUP (0) - 等待唤醒
- OPEN (1) - 开放（聚合中）
- LOCKED (2) - 已锁定（处理中）
- COMPLETE (3) - 已完成
- CANCELLED (4) - 已取消

### 新增字段

- wake_delay_ms - 唤醒延迟（毫秒），仅在 WAITING_WAKEUP 状态下非 NULL
- wake_adjustment_count - 等待期间收到新消息的调整次数

### 流程集成

**1. 消息到达时判断是否需要唤醒**：

- 查询最近的 COMPLETE buffer，检查 last_msg_time_ms 是否在 wake_window_ms 内
- 如果在窗口内 → 跳过唤醒，直接创建 OPEN buffer
- 如果超出窗口 → 创建 WAITING_WAKEUP buffer

**2. 等待期间收到新消息（含 typing_start / typing_end）**：

- 根据 wake_time_adjustment 算法调整 wake_delay_ms
- 统一重算 micro/macro/wake 三者对应的 `buffer_expires_at_ms`
- 计数规则：
  - TEXT：`wake_adjustment_count += 1`，并更新聚合内容
  - typing_start / typing_end：不写内容，但必须重算计时

### 与现有流程的关系

- 唤醒机制是 buffer 调度的一部分
- 锁定候选来自“已到期窗口”（`WAITING_WAKEUP` 或 `OPEN`）
- 初次对话（无历史 COMPLETE buffer）跳过唤醒，直接创建 OPEN buffer

详细设计参见 spec/ai/relationship-system.md#关系响应参数

## 整体流程

### 1. 入站缓冲（add_message_to_buffer）

**输入**：用户消息（含 msg_id、supports_typing、message_category、content、时间戳等）

**如果窗口存在**（合并消息）：

1. 根据 last_message_category 和当前 message_category 确定计时器操作
2. 更新窗口元数据（不存储 content）
3. 同时将消息内容写入 ai_conversation_items（见 [context.md](context.md)）

**如果窗口不存在**（创建新窗口）

同时将消息内容写入 ai_conversation_items。

### 2. 到期扫描与锁定（scheduler tick）

**周期性扫描**（间隔 100ms）

**对每个会话执行事务内锁定**（事务内）

锁定规则：

- 锁定候选来自已到期窗口（`WAITING_WAKEUP` 或 `OPEN`），按 `buffer_expires_at_ms <= now_ms` 判定。
- 旧 LOCKED 仅在抢占发生时取消。
- LOCKED/COMPLETE/CANCELLED 转换使用 CAS 条件更新。
- 禁止批量取消全部 OPEN。
- 新窗口锁定成功后，推进会话 `active_turn_version` 使抢占生效。

**并发处理**：唯一索引 `UNIQUE(user_qiao_id, instance_qiao_id) WHERE aggregate_state=2` 保证同会话最多一个 LOCKED，冲突时重试。

### 3. 执行与落地（processor）

**逻辑步骤**：

1. 读取 LOCKED 窗口
2. 从 ai_conversation_items 查询该 buffer 关联的所有用户消息
3. 构建完整上下文（见 [context.md](context.md)）
4. 发起 LLM 请求（流式或非流式）
5. 若检测到 `active_turn_version` 已切换，立即中止流式读取（早停可减少后续输出 tokens 费用）
6. 结果落地前二次校验：若该窗口仍为 LOCKED，则将该 buffer 窗口置 COMPLETE（CAS）
7. 若状态已变（CANCELLED/OPEN/不存在），丢弃结果（被抢占）

**重要说明**：

- 不在此阶段写入 assistant 消息到 ai_conversation_items
- assistant 消息在实际发送时写入（见 spec/ai/message-sending.md）
- 理由：保持 ImmutableSnowflakeModel 的不可变性，每条消息独立插入，记录真实发送时间

### 4. LLM 响应处理与消息发送

**流程**：

1. Buffer 通过 finalize 校验后，进入响应处理与发送：
   - 安全副作用：attack_detected、should_block（always-on）
   - 消息发送：send_ai_messages_with_typing
   - 会话副作用：memory_operations、score（首条发送门槛达成后独立执行）

2. 消息发送过程中：
   - 每发送一条消息，立即独立插入到 ai_conversation_items
   - 记录真实的发送时间（created_at）
   - 如果被打断，仅未发送 outgoing 写入 ai_conversation_state.pending_messages

3. 抢占导致未发送时，写入 ai_conversation_state.pending_messages.outgoing
4. Provider 投递失败走 outbox 重试链路，不写 ai_conversation_state.pending_messages

详细设计参见 spec/ai/message-sending.md

## 并发与时钟

- 并发安全：依赖数据库事务 + 唯一部分索引；不需要进程内 per-conversation 锁
- 时钟一致性：到期时间的写入与扫描优先使用 DB 时钟；若获取失败，使用进程时钟并记录 WARNING（见 `docs/spec/error-handling.md`）

## 错误与恢复

**重启恢复**：

扫描 `aggregate_state IN (0,1) AND buffer_expires_at_ms <= now_ms` 即可恢复处理。

**异常滞留**：

启动时会将 `WAITING_WAKEUP` / `OPEN` / `LOCKED` 的窗口统一置为 `CANCELLED`，用于释放滞留状态。
