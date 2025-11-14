# AI 消息处理技术文档（MVP 版）

本技术文档明确 AI 消息缓冲聚合、可抢占处理、并发与幂等策略，以及与数据库字段的对应关系。作为实现基线，代码与 SQL 以本稿为准。

## 目标

- 简洁：最少字段完成聚合与可抢占处理（KISS/YAGNI）。
- 可抢占：新消息到期后直接覆盖旧处理，不被旧请求阻塞。
- 幂等：结果落地前二次校验，旧请求结果丢弃。
- 职责分离：buffer 管理状态，conversation_items 存储内容。

## 架构设计

### 表结构分离

系统使用两个表实现职责分离：

1. **ai_message_buffer**：纯粹的消息聚合状态机
   - 管理双计时器（micro/macro）
   - 追踪窗口元数据（first/last msg_id, message_count）
   - 控制状态转换（OPEN → LOCKED → COMPLETE/CANCELLED）
   - **不存储消息内容**

2. **ai_conversation_items**：对话历史存储
   - 存储完整的消息内容（JSONB 格式）
   - 支持多模态内容（文本、图片、视频、工具调用等）
   - 提供上下文查询和审计功能
   - 标记攻击消息（is_excluded_from_context）

### ai_message_buffer 核心字段

- `aggregate_state`: 聚合状态（1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED）
- `micro_expires_at_ms`: 微计时器到期时间（毫秒时间戳），每条新消息重置，NULL 表示已取消
- `macro_expires_at_ms`: 宏计时器到期时间（毫秒时间戳），从 typing_start 开始计时，NULL 表示未设置
- `last_message_category`: 上一条消息类别（'CONTENT_TYPING', 'CONTENT_NO_TYPING', 'typing_start', 'typing_end'）
- `first_msg_id_client`: 窗口内第一条消息的客户端 ID
- `last_msg_id_client`: 窗口内最后一条消息的客户端 ID
- `message_count`: 窗口内消息数量
- `last_msg_time_ms`: 窗口最后一条消息的毫秒时间戳

### 约束与索引

- 同会话唯一锁（限制活跃处理窗口）：
  `UNIQUE(user_qiao_id, character_qiao_id) WHERE aggregate_state=2`
- 微计时器扫描索引：
  `CREATE INDEX idx_buffer_micro_expire ON ai_message_buffer(user_qiao_id, character_qiao_id, micro_expires_at_ms) WHERE aggregate_state=1 AND micro_expires_at_ms IS NOT NULL`
- 宏计时器扫描索引：
  `CREATE INDEX idx_buffer_macro_expire ON ai_message_buffer(user_qiao_id, character_qiao_id, macro_expires_at_ms) WHERE aggregate_state=1 AND macro_expires_at_ms IS NOT NULL`
- 时间基准：聚合到期相关计算/比较统一使用数据库时钟
  `NOW()` → `(EXTRACT(EPOCH FROM NOW())*1000)::BIGINT`

### 实现要点

- **新消息到达**：若存在"最近一条 state=OPEN"窗口，则更新元数据（last_msg_id_client, message_count, 计时器）；否则新建 `OPEN` 窗口。消息内容同时写入 `ai_conversation_items`。
- **触发处理（到期）**：在事务内先将该会话所有旧的 `OPEN/LOCKED` 标记为 `CANCELLED`，再将"最新且到期"的窗口置为 `LOCKED`，随后启动处理。
- **结果落地前校验**：仅当该窗口仍为 `LOCKED` 时写入 assistant 消息到 `ai_conversation_items` 并将 buffer 置为 `COMPLETE`；否则丢弃（被抢占的旧结果）。

### 设计动机

- 以状态机+唯一锁实现"新消息可抢占旧处理"，无需进程内锁与复杂协调。
- 职责分离：buffer 专注状态管理，conversation_items 专注数据存储，符合 SOLID 原则。

## 双计时器机制

### 设计原理

使用微计时器和宏计时器平衡响应速度与消息聚合：

- **微计时器**：每条新消息重置，快速响应（3-8秒）
- **宏计时器**：从 typing_start 开始计时，防止无限等待（32秒上限）
- **触发条件**：任一计时器到期即触发处理，两个计时器同时取消

### 消息类型与等待时间

从 `system_configs` 表获取配置：

- `CONTENT_TYPING`: supports_typing=true 的普通消息 → `message_buffer_normal_wait_ms`（默认 3000ms）
- `CONTENT_NO_TYPING`: supports_typing≠true 的普通消息 → `message_buffer_no_typing_wait_ms`（默认 8000ms）
- `typing_start`: 无对应时间，转为宏计时器 → `message_buffer_typing_total_wait_ms`（默认 32000ms）
- `typing_end`: → `message_buffer_typing_end_wait_ms`（默认 3000ms）

> ⚠️ 除非键名显式包含 `_ms`，`system_configs` 中的 AI conversation/archive 配置一律使用 **秒** 作为单位，禁止填入毫秒值。

### 状态转换规则

#### 无上一条消息（last_message_category = NULL）

| 当前消息类型 | 操作 |
|------------|------|
| CONTENT_TYPING | 设置微计时器（message_buffer_normal_wait_ms） |
| CONTENT_NO_TYPING | 设置微计时器（message_buffer_no_typing_wait_ms） |

#### 上一条为 CONTENT_TYPING

| 当前消息类型 | 操作 |
|------------|------|
| CONTENT_TYPING | 设置微计时器 |
| typing_start | 取消微计时器，设置宏计时器（message_buffer_typing_total_wait_ms） |

#### 上一条为 typing_start

| 当前消息类型 | 操作 |
|------------|------|
| CONTENT_TYPING | 取消宏计时器，设置微计时器 |
| typing_end | 设置微计时器（message_buffer_typing_end_wait_ms） |

#### 上一条为 typing_end

| 当前消息类型 | 操作 |
|------------|------|
| CONTENT_TYPING | 设置微计时器 |
| typing_start | 取消微计时器 |

#### 上一条为 CONTENT_NO_TYPING

| 当前消息类型 | 操作 |
|------------|------|
| CONTENT_NO_TYPING | 设置微计时器 |

#### 其他情况组合

不影响计时器且不记录为上一条消息。

## 唤醒机制（Wake Mechanism）

### 设计目标

模拟真人"看到消息后思考一段时间"的行为，使 AI 响应速度反映与用户的关系等级。

### 状态扩展

在原有状态基础上新增 WAITING_WAKEUP 状态（值为 0）：

- `WAITING_WAKEUP = 0`: 等待唤醒（新增）
- `OPEN = 1`: 开放（聚合中）
- `LOCKED = 2`: 已锁定（处理中）
- `COMPLETE = 3`: 已完成
- `CANCELLED = 4`: 已取消

### 新增字段

- `wake_expires_at_ms`: 唤醒计时器到期时间（毫秒时间戳），仅在 WAITING_WAKEUP 状态下非 NULL
- `wake_adjustment_count`: 等待期间收到新消息的调整次数

### 流程集成

1. **消息到达时判断是否需要唤醒**：
   - 查询最近的 COMPLETE buffer，检查 last_msg_time_ms 是否在 wake_window_ms 内
   - 如果在窗口内 → 跳过唤醒，直接创建 OPEN buffer
   - 如果超出窗口 → 创建 WAITING_WAKEUP buffer

2. **WAITING_WAKEUP → OPEN 转换**：
   - Scanner 扫描 wake_expires_at_ms 到期的 WAITING_WAKEUP buffer
   - 批量更新为 OPEN 状态，清空 wake_expires_at_ms
   - 进入现有的 buffer 聚合流程

3. **等待期间收到新消息**：
   - 根据 wake_time_adjustment 算法调整 wake_expires_at_ms
   - wake_adjustment_count += 1
   - 更新 buffer 内容

### 与现有流程的关系

- 唤醒机制在 buffer 流程**之前**，不影响现有的双计时器逻辑
- WAITING_WAKEUP 状态的 buffer 不参与 OPEN buffer 的查询和锁定
- 初次对话（无历史 COMPLETE buffer）跳过唤醒，直接创建 OPEN buffer

详细设计参见 [relationship-response-timing.md](relationship-response-timing.md)

## 整体流程

### 1) 入站缓冲（add_message_to_buffer）

**输入**：用户消息（含 client 侧 `msg_id`、`supports_typing`、`message_category`、`content`、时间戳等）

**逻辑**：

```sql
-- 查询最近的 OPEN 窗口
SELECT * FROM ai_message_buffer
WHERE user_qiao_id = $1 AND character_qiao_id = $2
  AND aggregate_state = 1
ORDER BY created_at DESC LIMIT 1;
```

**如果窗口存在**（合并消息）：

1. 根据 `last_message_category` 和当前 `message_category` 确定计时器操作
2. 更新窗口元数据（不存储 content）：

   ```sql
   UPDATE ai_message_buffer SET
     last_msg_id_client = $msg_id,
     last_msg_time_ms = $now_ms,
     message_count = message_count + 1,
     micro_expires_at_ms = $new_micro_expires,  -- 根据规则设置或 NULL
     macro_expires_at_ms = $new_macro_expires,  -- 根据规则设置或保持
     last_message_category = $current_category
   WHERE id = $window_id;
   ```

3. 同时将消息内容写入 `ai_conversation_items`（每条消息独立存储）

**如果窗口不存在**（创建新窗口）：

```sql
-- 创建新的 buffer 窗口
INSERT INTO ai_message_buffer (
  user_qiao_id, character_qiao_id, aggregate_state,
  first_msg_id_client, last_msg_id_client,
  message_count, micro_expires_at_ms, macro_expires_at_ms,
  last_message_category, last_msg_time_ms, created_at
) VALUES (
  $user_id, $char_id, 1,
  $msg_id, $msg_id,
  1, $micro_expires, NULL,  -- 新窗口宏计时器为 NULL
  $category, $now_ms, NOW()
);

-- 同时将消息内容写入 ai_conversation_items
INSERT INTO ai_conversation_items (
  user_qiao_id, character_qiao_id, role,
  content, content_preview, buffer_id, client_msg_ids,
  is_excluded_from_context, created_at
) VALUES (
  $user_id, $char_id, 'user',
  $content_jsonb, $preview, $buffer_id, ARRAY[$msg_id],
  false, NOW()
);
```

**计时器计算示例**（使用数据库时钟）：

```sql
-- 微计时器：当前时间 + 等待时间
micro_expires_at_ms = (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT + $wait_ms

-- 宏计时器：仅在 typing_start 时设置
macro_expires_at_ms = (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT + 32000
```

### 2) 到期扫描与锁定（scheduler tick）

**周期性扫描**（建议每秒 1 次）：

```sql
-- 查找任一计时器到期的窗口
SELECT * FROM ai_message_buffer
WHERE aggregate_state = 1
  AND (
    (micro_expires_at_ms IS NOT NULL AND micro_expires_at_ms <= $now_ms)
    OR
    (macro_expires_at_ms IS NOT NULL AND macro_expires_at_ms <= $now_ms)
  )
ORDER BY user_qiao_id, character_qiao_id, created_at;
```

**对每个会话执行抢占式锁定**（事务内）：

```sql
BEGIN;

-- 1. 取消该会话所有旧的 OPEN/LOCKED 窗口
UPDATE ai_message_buffer SET aggregate_state = 4  -- CANCELLED
WHERE user_qiao_id = $user_id AND character_qiao_id = $char_id
  AND aggregate_state IN (1, 2);

-- 2. 锁定最新且到期的窗口
UPDATE ai_message_buffer SET
  aggregate_state = 2,  -- LOCKED
  micro_expires_at_ms = NULL,  -- 清空计时器
  macro_expires_at_ms = NULL
WHERE id = $window_id AND aggregate_state = 1
RETURNING *;

COMMIT;
```

**并发处理**：唯一索引 `UNIQUE(user_qiao_id, character_qiao_id) WHERE aggregate_state=2` 保证同会话最多一个 LOCKED，冲突时重试。

### 3) 执行与落地（processor）

- 读取 `LOCKED` 窗口，从 `ai_conversation_items` 查询该 buffer 关联的所有用户消息。
- 构建完整上下文（包含历史对话），发起 Doubao 流式请求（SSE）。
- 若新窗口抢占发生，立即中止流式读取（早停可减少后续输出 tokens 费用）。
- 结果落地前二次校验：若该窗口仍为 `LOCKED`，则：
  - 将 assistant 响应写入 `ai_conversation_items`（JSONB 格式，直接存储 Doubao 返回的 content blocks）；
  - 将该 buffer 窗口置 `COMPLETE`。
- 若状态已变（CANCELLED/OPEN/不存在），丢弃结果（被抢占）。

**保存 assistant 消息示例**：

```sql
-- 保存 assistant 响应到 ai_conversation_items
INSERT INTO ai_conversation_items (
  user_qiao_id, character_qiao_id, role,
  content, content_preview, llm_config_id,
  is_excluded_from_context, created_at
) VALUES (
  $user_id, $char_id, 'assistant',
  $assistant_content_jsonb,  -- Doubao 返回的 content blocks
  $preview, $llm_config_id,
  false, NOW()
);

-- 标记 buffer 为 COMPLETE
UPDATE ai_message_buffer SET aggregate_state = 3
WHERE id = $buffer_id AND aggregate_state = 2;
```

### 4) 发送与失败重试

- 通过 LeanCloud 发送；失败写入 `message_delivery_failures`，按既有策略重试。

## 上下文构建

从 `ai_conversation_items` 查询对话历史，自动排除攻击消息：

```sql
-- 构建 LLM 上下文
SELECT role, content
FROM ai_conversation_items
WHERE user_qiao_id = $user_id
  AND character_qiao_id = $char_id
  AND is_excluded_from_context = false  -- 排除攻击消息
ORDER BY created_at DESC
LIMIT 20;
```

返回的 `content` 字段已经是 JSONB 数组格式，直接传递给 Doubao Responses API。

## Doubao 调用策略（与计费）

- 一律使用"流式输出" + 早停（SSE）：
  - 可以在"满足需求/被抢占"时立即停止，节省后续输出 tokens（输入 tokens 不变）。
  - 参考：`stream_options.include_usage` / `chunk_include_usage` 监控用量。
- 控制最大输出：配置 `max_tokens`（或深度思考模型的 `max_completion_tokens`）防止超预算。
- **不使用上下文缓存**：系统采用动态裁剪上下文和实时生成系统提示词，与 Doubao 缓存机制（要求前缀消息完全一致）存在根本性冲突。

## 并发与时钟

- 并发安全：依赖数据库事务 + 唯一部分索引；不需要进程内 per-conversation 锁。
- 时钟一致性：建议到期时间的写入与扫描均用 DB 时钟，避免多实例时间漂移。

## 错误与恢复

- 重启恢复：扫描 `aggregate_state=1 AND (micro_expires_at_ms <= now_ms OR macro_expires_at_ms <= now_ms)` 即可恢复处理。
- 异常滞留：定期清理长时间 `LOCKED` 的窗口（超限置 `CANCELLED` 或回到 `OPEN`），避免卡死（可在后续迭代加入）。

## 可选扩展（非 MVP）

- 处理轨迹审计：如需，可增加 `locked_at/canceled_at` 等审计列（当前不必需）。
- 归档策略：定期将 `ai_conversation_items` 中超过 14 天的记录迁移到 `ai_conversation_items_archive`。
