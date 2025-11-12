---
title: AI Contexts 架构重构方案
date: 2025-11-16
status: approved
---

## 背景与目标

系统已从 Chat Completions API 迁移至 Doubao Responses API，当前 `ai_contexts` 表存在严重的架构问题，需要彻底重构以支持：

1. **职责分离**：消息 buffer 状态管理与对话历史存储分离
2. **多模态支持**：为未来的图片/视频消息预留扩展能力
3. **安全隔离**：提示词攻击消息的标记与过滤

## 核心决策

### 1. 放弃 Doubao 上下文缓存

**原因**：系统采用动态裁剪上下文和实时生成系统提示词，与 Doubao 缓存机制（要求前缀消息完全一致）存在根本性冲突。

**影响**：

- 移除 `llm_session_cache` 表
- 移除 `llm_configs` 中的缓存相关字段
- 简化 LLM 服务层逻辑

详见：[llm_responses_migration.md](llm_responses_migration.md)

### 2. 内容存储策略

**决策**：使用 JSONB 存储 content 数组，与 Doubao Responses API 格式完全一致。

**理由**：
- **API 格式一致**：Doubao Responses API 使用 content 数组，直接存储避免转换
- **零成本扩展**：未来添加图片/视频只需在代码层面处理新 block 类型，无需 migration
- **代码逻辑统一**：从一开始就按 blocks 结构设计，避免维护两套逻辑
- **不违反 YAGNI**：选择合适的数据结构是架构设计，不是"添加未来功能"

**MVP 实施策略**：
- 数据库：使用 `content JSONB` 存储数组 `[{"type": "text", "text": "..."}]`
- 代码：只实现 text block 的处理逻辑
- 未来：添加 image/video block 的处理，表结构不变

### 3. 开发重构策略

- 当前处于开发重构阶段，数据库结构可以一次性修改到位，不需要保留 `ai_contexts` 或任何过渡表。
- 禁止实现双写、灰度切换、回退逻辑等历史包袱；所有上下游代码需要同步迁移到新结构。
- 迁移完成后必须清理相关旧代码（如 `ai_contexts` 读写、缓存链路等），避免遗留引用。

## 重构方案

### 表 1：ai_message_buffer（消息缓冲管理）

**职责**：纯粹的消息聚合状态机，不存储实际消息内容。

```sql
CREATE TABLE ai_message_buffer (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,

    -- Buffer 状态管理（来自 ai-message-processing.md）
    aggregate_state INTEGER NOT NULL,  -- 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED
    micro_expires_at_ms BIGINT,
    macro_expires_at_ms BIGINT,
    last_message_category VARCHAR(32),  -- 'CONTENT_TYPING', 'CONTENT_NO_TYPING', 'typing_start', 'typing_end'

    -- 消息窗口元数据
    first_msg_id_client VARCHAR(64),
    last_msg_id_client VARCHAR(64),
    message_count INTEGER NOT NULL DEFAULT 1,
    last_msg_time_ms BIGINT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- 唯一约束：同会话只能有一个 LOCKED 窗口
    CONSTRAINT uq_locked_buffer UNIQUE (user_qiao_id, character_qiao_id)
        WHERE aggregate_state = 2
);

-- 索引：微计时器扫描
CREATE INDEX idx_buffer_micro_expire
    ON ai_message_buffer(user_qiao_id, character_qiao_id, micro_expires_at_ms)
    WHERE aggregate_state = 1 AND micro_expires_at_ms IS NOT NULL;

-- 索引：宏计时器扫描
CREATE INDEX idx_buffer_macro_expire
    ON ai_message_buffer(user_qiao_id, character_qiao_id, macro_expires_at_ms)
    WHERE aggregate_state = 1 AND macro_expires_at_ms IS NOT NULL;

-- 索引：会话查询
CREATE INDEX idx_buffer_session
    ON ai_message_buffer(user_qiao_id, character_qiao_id, created_at DESC);
```

**关键字段说明**：

- `message_count`：记录合并了几条消息
- `first_msg_id_client` / `last_msg_id_client`：边界追踪，用于客户端确认
- **不存储 content**：消息内容由 `ai_conversation_items` 表管理

### 表 2：ai_conversation_items（对话历史）

**职责**：存储完整的对话历史，支持上下文构建和审计。直接映射 Doubao Responses API content 数组。

```sql
CREATE TABLE ai_conversation_items (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,

    -- 消息角色
    role VARCHAR(20) NOT NULL,  -- 'system', 'user', 'assistant'

    -- 消息内容（JSONB 数组，直接存储 Responses API blocks）
    content JSONB NOT NULL,  -- [{"type": "text", "text": "..."}, ...]

    -- 纯文本预览（便于检索和后台展示）
    content_preview TEXT,

    -- 关联信息
    buffer_id BIGINT,  -- 关联到 ai_message_buffer.id（仅 user 消息）
    llm_config_id INTEGER,  -- 使用的 LLM 配置（仅 assistant 消息）

    -- 客户端消息 ID（合并场景下为数组）
    client_msg_ids TEXT[],

    -- 安全标记
    is_excluded_from_context BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否从 LLM 上下文中剔除（攻击/敏感内容）

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- 外键
    FOREIGN KEY (buffer_id) REFERENCES ai_message_buffer(id) ON DELETE SET NULL,
    FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id) ON DELETE SET NULL,

    -- 检查约束：role='user' 时必须携带 buffer_id
    CONSTRAINT chk_user_buffer CHECK (
        (role = 'user' AND buffer_id IS NOT NULL) OR
        (role != 'user' AND buffer_id IS NULL)
    )
);

-- 索引：会话查询（最常用）
CREATE INDEX idx_conv_items_session
    ON ai_conversation_items(user_qiao_id, character_qiao_id, created_at DESC);

-- 索引：Buffer 关联
CREATE INDEX idx_conv_items_buffer
    ON ai_conversation_items(buffer_id) WHERE buffer_id IS NOT NULL;

-- 索引：排除内容筛选
CREATE INDEX idx_conv_items_excluded
    ON ai_conversation_items(user_qiao_id, character_qiao_id, is_excluded_from_context, created_at DESC);
```

**Block 类型约定**（与 Doubao Responses API 一致）：

- 输入：`input_text`, `input_image`, `input_audio`, `input_video`
- 输出：`output_text`, `output_audio`, `reasoning`
- 工具：`tool_call`, `tool_result`

**示例数据**：

```json
// 纯文本消息
[{"type": "text", "text": "你好"}]

// 多模态消息
[
  {"type": "text", "text": "这是什么？"},
  {"type": "image", "image_url": "https://...", "detail": "high"}
]

// 工具调用
[{
  "type": "tool_call",
  "call_id": "call_abc123",
  "name": "get_weather",
  "arguments": "{\"location\":\"北京\"}"
}]

// Assistant 响应（含 reasoning）
[
  {"type": "text", "text": "北京今天晴天"},
  {"type": "reasoning", "text": "用户询问天气..."}
]
```

### 表 3：ai_conversation_items_archive（归档表）

**职责**：长期存储，定期从主表迁移历史数据。

```sql
CREATE TABLE ai_conversation_items_archive (
    -- 与 ai_conversation_items 完全相同的结构
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    content_preview TEXT,
    buffer_id BIGINT,
    llm_config_id INTEGER,
    client_msg_ids TEXT[],
    is_excluded_from_context BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    archived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

**归档策略**：

- 定期任务（pg_cron / APScheduler）每日搬迁 `created_at < NOW() - INTERVAL '14 days'` 的记录
- 归档后立即从主表删除对应记录，并执行 `VACUUM ANALYZE ai_conversation_items` 保持索引健康

## 核心业务逻辑

### 1. Buffer 消息追踪

**说明**：Buffer 只管理状态机，不存储消息内容。消息内容直接写入 `ai_conversation_items`。

```python
async def add_message_to_buffer(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    message_content: str,
    msg_id_client: str,
    message_category: str,
    supports_typing: bool,
) -> int:
    """Add message to buffer, track metadata only."""

    # 查询最近的 OPEN 窗口
    buffer = await get_open_buffer(db, user_qiao_id, character_qiao_id)

    if buffer:
        # 更新窗口元数据（不存储 content）
        buffer.last_msg_id_client = msg_id_client
        buffer.message_count += 1
        buffer.last_msg_time_ms = get_current_ms()

        # 更新计时器（根据 ai-message-processing.md 规则）
        update_timers(buffer, message_category, supports_typing)

        await db.flush()
        return buffer.id
    else:
        # 创建新窗口
        buffer = AIMessageBuffer(
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            aggregate_state=AggregateState.OPEN,
            first_msg_id_client=msg_id_client,
            last_msg_id_client=msg_id_client,
            message_count=1,
            last_message_category=message_category,
            # ... 设置计时器
        )
        db.add(buffer)
        await db.flush()
        return buffer.id
```

### 2. 保存对话历史

```python
async def save_conversation_result(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    buffer: AIMessageBuffer,
    user_messages: List[str],  # 窗口内的所有用户消息
    assistant_content: List[Dict[str, Any]],  # Doubao 返回的 content blocks
    llm_config_id: int,
) -> None:
    """Save conversation to history after LLM response."""

    # 1. 合并用户消息为单个 text block
    merged_text = "\n".join(user_messages)

    # 2. 检测提示词攻击
    is_excluded = await detect_prompt_injection(merged_text)

    # 3. 保存 user 消息（JSONB 格式）
    user_item = AIConversationItem(
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        role="user",
        content=[{"type": "text", "text": merged_text}],  # JSONB 数组
        content_preview=merged_text[:200],  # 预览前 200 字符
        buffer_id=buffer.id,
        client_msg_ids=get_client_msg_ids(buffer),
        is_excluded_from_context=is_excluded,
    )
    db.add(user_item)

    if is_excluded:
        logger.warning("prompt_injection_detected",
                      user_qiao_id=user_qiao_id,
                      buffer_id=buffer.id)

    # 4. 保存 assistant 消息（JSONB 格式，直接存储 Doubao 返回的 blocks）
    assistant_preview = extract_text_preview(assistant_content)
    assistant_item = AIConversationItem(
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        role="assistant",
        content=assistant_content,  # 直接存储 Doubao 返回的 blocks
        content_preview=assistant_preview,
        llm_config_id=llm_config_id,
        is_excluded_from_context=False,
    )
    db.add(assistant_item)

    # 5. 标记 buffer 为 COMPLETE
    buffer.aggregate_state = AggregateState.COMPLETE

    await db.commit()


def extract_text_preview(content_blocks: List[Dict[str, Any]]) -> str:
    """Extract text preview from content blocks."""
    texts = []
    for block in content_blocks:
        if block.get("type") == "text":
            texts.append(block.get("text", ""))
    return " ".join(texts)[:200]
```

### 3. 构建 LLM 上下文

```python
async def build_conversation_context(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Build conversation context for LLM request, excluding attacks."""

    result = await db.execute(
        select(AIConversationItem)
        .where(
            AIConversationItem.user_qiao_id == user_qiao_id,
            AIConversationItem.character_qiao_id == character_qiao_id,
            AIConversationItem.is_excluded_from_context == False,  # 排除攻击消息
        )
        .order_by(desc(AIConversationItem.created_at))
        .limit(limit)
    )

    # 反转顺序（最早的在前）
    items = list(reversed(result.scalars().all()))

    # 直接返回 Doubao Responses API 格式
    return [
        {"role": item.role, "content": item.content}  # content 已经是 JSONB 数组
        for item in items
    ]
```

## 提示词攻击防护

### 策略：标记保留 + 查询过滤

**原则**：

- 攻击消息仍然保存在数据库（审计完整性）
- 默认查询自动排除（自动隔离）
- 管理员可查看完整历史（灵活控制）

**实现**：

```python
async def get_conversation_items(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    limit: int = 20,
    include_excluded: bool = False,  # 默认排除
) -> List[AIConversationItem]:
    """Get conversation items with optional filtering."""

    query = (
        select(AIConversationItem)
        .where(
            AIConversationItem.user_qiao_id == user_qiao_id,
            AIConversationItem.character_qiao_id == character_qiao_id,
        )
    )

    # 默认排除攻击消息
    if not include_excluded:
        query = query.where(AIConversationItem.is_excluded_from_context == False)

    query = query.order_by(desc(AIConversationItem.created_at)).limit(limit)

    result = await db.execute(query)
    return list(reversed(result.scalars().all()))
```

## 迁移路径

由于正处在开发重构阶段，直接切换最为高效，迁移策略如下：

1. **单次 Migration 改造**：使用 Alembic 脚本直接删除 `ai_contexts`/`ai_contexts_archive`，创建 `ai_message_buffer` 与 `ai_conversation_history` 新结构（含 `content`、`client_msg_ids`、`is_attack` 等字段）。
2. **同步代码更新**：同一个 PR 内更新 ORM、服务、查询、管理后台等所有触点，确保上线即读取/写入新结构。
3. **脚本级数据导入（可选）**：如需保留样例，可在本地一次性跑 SQL，将仍有价值的旧数据写入新表；不提供长时间双写方案。
4. **彻底清理旧逻辑**：移除 `ai_contexts` 相关 CRUD、旧缓存链路（含 `llm_session_cache`）以及所有回退开关，确保不存在遗留引用。

> 注意：禁止实现双写、灰度切换、回退脚本等“安全网”，否则会让新架构再次被历史包袱拖累。

## 架构优势

### 1. 职责清晰分离

- `ai_message_buffer`：纯状态机，管理消息聚合逻辑
- `ai_conversation_history`：纯数据存储，记录对话历史
- 符合 SOLID 的单一职责原则

### 2. 简单至上（KISS）

- MVP 阶段使用 TEXT 字段，避免过度设计
- 未来需要时可平滑迁移到 JSONB

### 3. 精益求精（YAGNI）

- 不为"未来可能"的多模态功能现在就设计复杂结构
- 当真正需要时再扩展

### 4. 安全性

- 提示词攻击消息自动隔离
- 保留审计记录便于安全分析

### 5. 性能优化

- 独立的 buffer 表减少对话历史表的写入压力
- 归档表支持长期存储，降低主表查询压力
- 针对性索引优化常用查询

## 相关文档

- [AI 消息处理技术文档](ai-message-processing.md) - Buffer 状态机设计
- [LLM Responses 迁移记录](llm_responses_migration.md) - Responses API 集成与缓存决策

## 当前排查结果（2025-XX-XX）

> 记录本轮审查中发现的偏差，作为后续实施路线的补充说明。

1. **（已完成）数据库 schema 与 ORM 对齐**
   - Alembic/初始化 SQL/ORM 已切换至 `ai_conversation_items` JSONB 结构，`ai_message_buffer` 也只保留状态字段，并将 `ai_request_logs.context_id` 重命名为 `conversation_item_id`；ORM 使用 `AIConversationItem`/`AIConversationItemArchive`。
2. **（已完成）Buffer 与数据访问层切换至新表**
   - `services/message/processing/buffer.py` 创建/合并窗口时直接落库 `ai_conversation_items`（含 `client_msg_ids`），`conversation_memory` 的归档逻辑也改为消费 `get_items_for_archiving`。
   - 仍待调整：`conversation_flow`/`conversation_prompt` 的上下文构建目前将 blocks 压扁为纯文本；需要改写为直接传递 Doubao Responses 的 `content` 数组。
3. **Responses Session Cache 未完全移除**
   - 尽管迁移脚本开头已 `DROP TABLE llm_session_cache`，但模型 (`models/llm/cache.py`)、服务 (`services/llm/cache.py`)、Admin 视图、诊断脚本和 LLM client 仍依赖相关字段。
   - `LLMConfig` 及 Admin/Pydantic 层继续暴露 `enable_caching/cache_strategy/cache_ttl_seconds`，与“放弃 Doubao 缓存”决策冲突。

### 后续实施顺序

1. **Schema & ORM**：按本文档最终版本改造 `ai_message_buffer` + `ai_conversation_items`（JSONB blocks），同步 Alembic、init SQL、ORM 导出。
2. **Data Access & Buffer Flow**：已完成 `context_queries/updates/transactions` 与 Buffer/归档改造，接下来重点是让 `conversation_flow`/`conversation_prompt` 直接消费 JSONB blocks 并提供多模态上下文。
3. **Admin & Logging**：更新请求日志、Admin 视图、统计脚本，全部引用 `ai_conversation_items` 与新的 `conversation_item_id`；去除任何 `ai_contexts`/`ai_conversation_history` 文案。
4. **LLM 客户端**：删除 session cache 全链路（模型、服务、Admin、诊断脚本、LLMConfig 字段、client/provider caching 参数），完成后回归测试完整会话流程并验证日志字段。

> 完成上述 4 步后，再依据 ai-message-processing.md 进行缓冲/到期/归档回归测试。

## 最新进展（2025-02-14）

1. **会话 ID 语义统一**
   - `process_conversation` 及其调用链（scanner、admin 测试执行器）已统一使用 `buffer_id`（锁定窗口）和 `assistant_item_id`（落库会话行），杜绝了“context_id” 多义性导致的排错困难。
   - `ai_request_logs` 与 Starlette-Admin 现仅暴露 `conversation_item_id`，所有对话日志都能准确回溯到 `ai_conversation_items` 行。

2. **Buffer/会话工具链补全**
   - 消息 buffer 服务现在暴露 `is_buffer_cancelled` / `finalize_buffer_if_locked` / `mark_conversation_item_as_attack` 语义明确的入口，避免循环依赖风险。
   - 新增 `backend/scripts/devtools/run_llm_responses_flow.py`，用于在无 session cache 的前提下快速回归 Responses API（支持工具、Schema 覆盖）。

3. **Session cache 诊断已剔除**
   - 诊断脚本与业务代码不再引用 `services.llm.cache`，彻底落地“放弃 Doubao 缓存”的决策；后续只需维护 Responses API 原生的 `cache_hit` 指标。
