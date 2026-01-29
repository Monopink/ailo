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
- 追踪窗口元数据（first/last msg_id, message_count）
- 控制状态转换（WAITING_WAKEUP → OPEN → LOCKED → COMPLETE/CANCELLED）
- **不存储消息内容**

**ai_conversation_items**：对话历史存储

- 存储扁平字段消息（message_type/text_content/media_url/media_metadata）
- 支持多模态内容（文本、图片、音频等）
- 提供上下文查询和审计功能
- 标记攻击消息（is_excluded_from_context）

详见 [context.md](context.md)

### ai_message_buffer 核心字段

完整表结构见 [data-dict/ai-conversation.md](../../data-dict/ai-conversation.md#ai_message_buffer)

本文档关注的关键字段：

- aggregate_state - 聚合状态（0=WAITING_WAKEUP, 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED）
- micro_expires_at_ms - 微计时器到期时间（毫秒时间戳），NULL 表示已取消
- macro_expires_at_ms - 宏计时器到期时间（毫秒时间戳），NULL 表示未设置
- wake_expires_at_ms - 唤醒计时器到期时间（仅 WAITING_WAKEUP 状态）
- last_message_category - 上一条消息类别（CONTENT_TYPING/CONTENT_NO_TYPING/typing_start/typing_end）
- first_msg_id_client - 窗口内第一条消息的客户端 ID
- last_msg_id_client - 窗口内最后一条消息的客户端 ID
- message_count - 窗口内消息数量
- last_msg_time_ms - 窗口最后一条消息的毫秒时间戳

### 约束与索引

- 同会话唯一锁：`UNIQUE(user_qiao_id, instance_qiao_id) WHERE aggregate_state=2`
- 微计时器扫描索引：`idx_buffer_micro_expire`
- 宏计时器扫描索引：`idx_buffer_macro_expire`
- 时间基准：统一使用数据库时钟 `(EXTRACT(EPOCH FROM NOW())*1000)::BIGINT`

## 双计时器机制

### 设计原理

使用微计时器和宏计时器平衡响应速度与消息聚合：

- 微计时器 - 每条新消息重置，快速响应 - 默认 3-8秒
- 宏计时器 - 从 typing_start 开始计时，防止无限等待 - 默认 32秒上限

**触发条件**：任一计时器到期即触发处理，两个计时器同时取消。

### 消息类型与等待时间

从 system_configs 表获取配置：

- CONTENT_TYPING - message_buffer_normal_wait_ms - 默认 3000ms
- CONTENT_NO_TYPING - message_buffer_no_typing_wait_ms - 默认 8000ms
- typing_start - message_buffer_typing_total_wait_ms - 默认 32000ms
- typing_end - message_buffer_typing_end_wait_ms - 默认 3000ms

### 状态转换规则

#### 无上一条消息（last_message_category = NULL）

- CONTENT_TYPING → 设置微计时器（message_buffer_normal_wait_ms）
- CONTENT_NO_TYPING → 设置微计时器（message_buffer_no_typing_wait_ms）

#### 上一条为 CONTENT_TYPING

- CONTENT_TYPING → 设置微计时器
- typing_start → 取消微计时器，设置宏计时器

#### 上一条为 typing_start

- CONTENT_TYPING → 取消宏计时器，设置微计时器
- typing_end → 设置微计时器（message_buffer_typing_end_wait_ms）

#### 上一条为 typing_end

- CONTENT_TYPING → 设置微计时器
- typing_start → 取消微计时器

#### 上一条为 CONTENT_NO_TYPING

- CONTENT_NO_TYPING → 设置微计时器

#### 其他情况组合

不影响计时器且不记录为上一条消息。

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

- wake_expires_at_ms - 唤醒计时器到期时间（毫秒时间戳），仅在 WAITING_WAKEUP 状态下非 NULL
- wake_adjustment_count - 等待期间收到新消息的调整次数

### 流程集成

**1. 消息到达时判断是否需要唤醒**：

- 查询最近的 COMPLETE buffer，检查 last_msg_time_ms 是否在 wake_window_ms 内
- 如果在窗口内 → 跳过唤醒，直接创建 OPEN buffer
- 如果超出窗口 → 创建 WAITING_WAKEUP buffer

**2. WAITING_WAKEUP → OPEN 转换**：

- Scanner 扫描 wake_expires_at_ms 到期的 WAITING_WAKEUP buffer
- 批量更新为 OPEN 状态，清空 wake_expires_at_ms
- 进入现有的 buffer 聚合流程

**3. 等待期间收到新消息**：

- 根据 wake_time_adjustment 算法调整 wake_expires_at_ms
- wake_adjustment_count += 1
- 更新 buffer 内容

### 与现有流程的关系

- 唤醒机制在 buffer 流程**之前**，不影响现有的双计时器逻辑
- WAITING_WAKEUP 状态的 buffer 不参与 OPEN buffer 的查询和锁定
- 初次对话（无历史 COMPLETE buffer）跳过唤醒，直接创建 OPEN buffer

详细设计参见 spec/ai/relationship-system.md#关系响应参数

## 整体流程

### 1. 入站缓冲（add_message_to_buffer）

**输入**：用户消息（含 msg_id、supports_typing、message_category、content、时间戳等）

**查询最近的 OPEN 窗口**：

```sql
SELECT * FROM ai_message_buffer
WHERE user_qiao_id = $1 AND instance_qiao_id = $2
  AND aggregate_state = 1
ORDER BY created_at DESC LIMIT 1;
```

**如果窗口存在**（合并消息）：

1. 根据 last_message_category 和当前 message_category 确定计时器操作
2. 更新窗口元数据（不存储 content）：

```sql
UPDATE ai_message_buffer SET
  last_msg_id_client = $msg_id,
  last_msg_time_ms = $now_ms,
  message_count = message_count + 1,
  micro_expires_at_ms = $new_micro_expires,
  macro_expires_at_ms = $new_macro_expires,
  last_message_category = $current_category
WHERE id = $window_id;
```

3. 同时将消息内容写入 ai_conversation_items（见 [context.md](context.md)）

**如果窗口不存在**（创建新窗口）：

```sql
INSERT INTO ai_message_buffer (
  user_qiao_id, instance_qiao_id, aggregate_state,
  first_msg_id_client, last_msg_id_client,
  message_count, micro_expires_at_ms, macro_expires_at_ms,
  last_message_category, last_msg_time_ms, created_at
) VALUES (
  $user_id, $char_id, 1,
  $msg_id, $msg_id,
  1, $micro_expires, NULL,
  $category, $now_ms, NOW()
);
```

同时将消息内容写入 ai_conversation_items。

**计时器计算**：

```sql
-- 微计时器：当前时间 + 等待时间
micro_expires_at_ms = (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT + $wait_ms

-- 宏计时器：仅在 typing_start 时设置
macro_expires_at_ms = (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT + 32000
```

### 2. 到期扫描与锁定（scheduler tick）

**周期性扫描**（建议每秒 1 次）：

```sql
SELECT * FROM ai_message_buffer
WHERE aggregate_state = 1
  AND (
    (micro_expires_at_ms IS NOT NULL AND micro_expires_at_ms <= $now_ms)
    OR
    (macro_expires_at_ms IS NOT NULL AND macro_expires_at_ms <= $now_ms)
  )
ORDER BY user_qiao_id, instance_qiao_id, created_at;
```

**对每个会话执行抢占式锁定**（事务内）：

```sql
BEGIN;

-- 1. 取消该会话所有旧的 OPEN/LOCKED 窗口
UPDATE ai_message_buffer SET aggregate_state = 4
WHERE user_qiao_id = $user_id AND instance_qiao_id = $char_id
  AND aggregate_state IN (1, 2);

-- 2. 锁定最新且到期的窗口
UPDATE ai_message_buffer SET
  aggregate_state = 2,
  micro_expires_at_ms = NULL,
  macro_expires_at_ms = NULL
WHERE id = $window_id AND aggregate_state = 1
RETURNING *;

COMMIT;
```

**并发处理**：唯一索引 `UNIQUE(user_qiao_id, instance_qiao_id) WHERE aggregate_state=2` 保证同会话最多一个 LOCKED，冲突时重试。

### 3. 执行与落地（processor）

**逻辑步骤**：

1. 读取 LOCKED 窗口
2. 从 ai_conversation_items 查询该 buffer 关联的所有用户消息
3. 构建完整上下文（见 [context.md](context.md)）
4. 发起 Doubao 流式请求（SSE）
5. 若新窗口抢占发生，立即中止流式读取（早停可减少后续输出 tokens 费用）
6. 结果落地前二次校验：若该窗口仍为 LOCKED，则将该 buffer 窗口置 COMPLETE
7. 若状态已变（CANCELLED/OPEN/不存在），丢弃结果（被抢占）

**标记 buffer 完成**：

```sql
UPDATE ai_message_buffer SET aggregate_state = 3
WHERE id = $buffer_id AND aggregate_state = 2;
```

**重要说明**：

- ❌ 不在此阶段写入 assistant 消息到 ai_conversation_items
- ✅ assistant 消息在实际发送时写入（见 spec/ai/message-sending.md）
- 理由：保持 ImmutableSnowflakeModel 的不可变性，每条消息独立插入，记录真实发送时间

### 4. LLM 响应处理与消息发送

**架构决策**：消息发送不再是 buffer 处理流程的一部分，而是由 process_llm_response 统一处理。

**流程**：

1. Buffer 标记为 COMPLETE 后，调用 process_llm_response 处理 LLM 响应中的所有操作：
   - attack_detected：标记攻击消息
   - should_block：拉黑用户
   - memory_operations：更新记忆
   - score：更新关系分数
   - **消息发送**：通过 send_ai_messages_with_typing 异步发送消息

2. 消息发送过程中：
   - 每发送一条消息，立即独立插入到 ai_conversation_items
   - 记录真实的发送时间（created_at）
   - 如果被打断，未发送的消息写入 ai_conversation_state.pending_messages

3. 消息发送失败时，写入 ai_conversation_state.pending_messages，等待下次对话时由 LLM 重新处理

详细设计参见 spec/ai/message-sending.md

## 并发与时钟

- 并发安全：依赖数据库事务 + 唯一部分索引；不需要进程内 per-conversation 锁
- 时钟一致性：建议到期时间的写入与扫描均用 DB 时钟，避免多实例时间漂移

## 错误与恢复

**重启恢复**：

扫描 `aggregate_state=1 AND (micro_expires_at_ms <= now_ms OR macro_expires_at_ms <= now_ms)` 即可恢复处理。

**异常滞留**：

定期清理长时间 LOCKED 的窗口（超限置 CANCELLED 或回到 OPEN），避免卡死（可在后续迭代加入）。

## 可选扩展（非 MVP）

- 处理轨迹审计：如需，可增加 locked_at/canceled_at 等审计列（当前不必需）
- 归档策略：定期将 ai_conversation_items 中超过 14 天的记录迁移到 ai_conversation_items_archive
- 归档后立即从主表删除对应记录，并执行 VACUUM ANALYZE ai_conversation_items 保持索引健康
