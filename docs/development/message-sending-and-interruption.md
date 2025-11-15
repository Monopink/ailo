# AI 消息发送与打断机制技术文档

本文档描述对话消息的存储格式、LLM 请求流程、消息发送流程（包括打字时间模拟、分批发送、打断机制）等完整实现细节。

## 目录

- [设计目标](#设计目标)
- [架构概览](#架构概览)
- [数据库设计](#数据库设计)
- [核心模块](#核心模块)
- [完整流程](#完整流程)
- [配置说明](#配置说明)
- [打断机制](#打断机制)
- [迁移指南](#迁移指南)

---

## 设计目标

### 核心需求

1. **简单至上**：使用最简单的数据结构存储消息（简单字段而非复杂 JSON）
2. **职责分离**：业务层、LLM 层、数据库层职责清晰
3. **依赖倒置**：业务层不依赖 LLM 提供商格式
4. **打字时间模拟**：根据消息内容和 `typing_speed_wpm`（词/分钟）计算等待时间，运行时若配置缺失或异常则回退到 35 WPM
5. **分批发送**：先发送 `outgoing_messages`，等待后再发送 `followup_messages`
6. **打断机制**：用户发送新消息时，应能立即停止当前正在进行的发送任务（MVP 阶段仅保证同实例打断）
7. **未发送消息处理**：将被打断的消息附加到下一次 LLM 请求的 system prompt 中
8. **消息独立存储**：每条发送成功的消息独立插入到 `ai_conversation_items`，保持不可变性（继承 `ImmutableSnowflakeModel`）

### 为什么不用 JSON 内容块？

**⚠️ 重要架构变更**：从 JSONB 内容块改为简单字段存储

**旧设计问题**：

```json
// 旧设计：存储 LLM 提供商格式
content: [
  {"type": "input_text", "text": "Hello"},
  {"type": "input_image", "image_url": {"url": "..."}}
]
```

❌ 存储的是 LLM 提供商格式（Doubao Responses API），违反依赖倒置
❌ 为"一条消息包含多个块"增加复杂度，但实际场景不需要
❌ 查询和分析困难，需要额外的 `content_preview` 字段
❌ 违反 YAGNI 原则，MVP 阶段用不到

**实际使用场景**：

- 微信：一条消息 = 一段文字 OR 一张图片 OR 一段语音
- 不存在"一条消息既有文字又有图片"的情况
- LLM 回复：纯文本（未来可能多条消息，但不是一条消息的多个块）

**新设计优势**：

```python
# 新设计：简单字段存储
message_type: str = "text"
text_content: str = "Hello"
media_url: Optional[str] = None
media_metadata: Optional[Dict] = None
```

✅ 极致简单（KISS）
✅ 查询直观：`WHERE text_content LIKE '%关键词%'`
✅ 不需要 `content_preview`
✅ 数据库原生全文搜索
✅ 符合实际使用场景

---

## 架构概览

### 职责边界

```
┌─────────────────────────────────────────────────────────┐
│ 数据库层 (PostgreSQL)                                    │
│ - 存储消息（简单字段：message_type + text_content）      │
│ - 提供查询接口                                           │
└─────────────────────────────────────────────────────────┘
                          ↓ ORM 对象
┌─────────────────────────────────────────────────────────┐
│ 业务层 (conversation_flow.py)                           │
│ - 查询数据库获取消息                                      │
│ - 转换为业务格式字典                                      │
│ - 处理业务逻辑（攻击检测、关系更新等）                     │
└─────────────────────────────────────────────────────────┘
                          ↓ 业务格式字典
┌─────────────────────────────────────────────────────────┐
│ LLM 层 (llm_client.py + converters/)                    │
│ - 接收业务格式字典                                        │
│ - 转换为 LLM 提供商格式（Doubao Responses API）          │
│ - 合并连续相同 role 的消息                               │
│ - 调用 LLM API                                           │
└─────────────────────────────────────────────────────────┘
                          ↓ LLM 响应
┌─────────────────────────────────────────────────────────┐
│ 发送层 (sender.py)                                       │
│ - 打字时间模拟                                           │
│ - 分批发送（outgoing → followup）                        │
│ - 打断控制（asyncio.Event）                              │
│ - 独立插入消息到数据库（简单字段）                        │
└─────────────────────────────────────────────────────────┘
```

### 数据流示例

```python
# 1. 数据库层：ORM 对象（简单字段）
AIConversationItem(
    role="user",
    message_type="text",
    text_content="你好",
)

# 2. 业务层：业务格式字典
{
    "role": "user",
    "message_type": "text",
    "text_content": "你好"
}

# 3. LLM 层：Doubao Responses API 格式
{
    "role": "user",
    "content": [{"type": "input_text", "text": "你好"}]
}
```

### 模块划分

```
backend/app/services/
├── message/
│   ├── processing/
│   │   ├── buffer.py                      # 消息 buffer 聚合
│   │   ├── scanner.py                     # 扫描到期 buffer
│   │   └── sender.py                      # 消息发送和打断
│   └── delivery/
│       └── leancloud.py                   # LeanCloud 发送
├── llm/
│   ├── llm_client.py                      # LLM 调用入口
│   └── converters/
│       ├── __init__.py                    # Converter 工厂
│       └── responses_format.py            # 格式转换 + 合并连续 role
└── ai/
    └── conversation_flow.py               # 对话流程处理
```

### 职责分离

| 层级 | 职责 | 示例 |
|------|------|------|
| **数据库层** | 存储消息（简单字段） | `message_type="text"`, `text_content="你好"` |
| **业务层** | 查询并转换为业务格式 | `{"role": "user", "message_type": "text", "text_content": "你好"}` |
| **LLM 适配层** | 转换为 LLM 格式 + 合并连续 role | `{"role": "user", "content": [{"type": "input_text", "text": "你好"}]}` |
| **发送层** | 打字模拟 + 打断控制 + 独立插入 | `sender.py` |

---

## 数据库设计

### 1. `ai_conversation_items` 表（⚠️ 重要变更）

**⚠️ 架构变更**：从 JSONB 内容块改为简单字段存储

**旧设计（需要修改）**：

```sql
-- ❌ 旧设计：使用 JSONB 存储 LLM 格式
content JSONB NOT NULL,
content_preview TEXT,
```

**新设计（目标结构）**：

```sql
-- ✅ 新设计：使用简单字段存储
CREATE TABLE ai_conversation_items (
    id BIGINT PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    role VARCHAR(20) NOT NULL,

    -- 简单字段存储内容（新增）
    message_type VARCHAR(20) NOT NULL DEFAULT 'text',
    text_content TEXT,
    media_url TEXT,
    media_metadata JSONB,

    client_msg_ids TEXT[] NOT NULL DEFAULT '{}',
    buffer_id BIGINT,
    is_excluded_from_context BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- 约束
    CONSTRAINT ck_ai_conversation_items_content CHECK (
        (message_type = 'text' AND text_content IS NOT NULL AND media_url IS NULL)
        OR (message_type IN ('image', 'audio') AND media_url IS NOT NULL)
    ),
    CONSTRAINT ck_ai_conversation_items_user_buffer CHECK (
        (role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user')
    )
);

-- 索引
CREATE INDEX idx_ai_conv_items_session
ON ai_conversation_items(user_qiao_id, character_qiao_id, created_at);

CREATE INDEX idx_ai_conv_items_buffer
ON ai_conversation_items(buffer_id)
WHERE buffer_id IS NOT NULL;

CREATE INDEX idx_ai_conv_items_excluded
ON ai_conversation_items(user_qiao_id, character_qiao_id, created_at)
WHERE is_excluded_from_context = true;

-- 全文搜索索引（需要 pg_trgm 扩展）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_ai_conv_items_text_search
ON ai_conversation_items USING gin(text_content gin_trgm_ops);

-- 字段注释
COMMENT ON COLUMN ai_conversation_items.message_type IS
  'Message type: text/image/audio';
COMMENT ON COLUMN ai_conversation_items.text_content IS
  'Text content (required for message_type=text)';
COMMENT ON COLUMN ai_conversation_items.media_url IS
  'Media URL (required for message_type=image/audio)';
COMMENT ON COLUMN ai_conversation_items.media_metadata IS
  'Media metadata: {"width": 800, "height": 600} for image, {"duration": 10, "transcript": "..."} for audio';
COMMENT ON COLUMN ai_conversation_items.buffer_id IS
  'Associated buffer ID. For user: aggregation buffer. For assistant: triggering buffer.';
```

**字段说明**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `message_type` | VARCHAR(20) | 消息类型 | `text`, `image`, `audio` |
| `text_content` | TEXT | 文本内容（`message_type=text` 时必填） | `"你好"` |
| `media_url` | TEXT | 媒体 URL（`message_type=image/audio` 时必填） | `"https://..."` |
| `media_metadata` | JSONB | 媒体元数据（可选） | `{"width": 800, "height": 600}` |

**约束规则**：

- **内容约束**：
  - `message_type='text'` 时：`text_content` 必填，`media_url` 必须为 NULL
  - `message_type='image'/'audio'` 时：`media_url` 必填
- **buffer_id 约束**：
  - `role='user'` 时：`buffer_id` 必填（关联到聚合 buffer）
  - `role='assistant'` 时：`buffer_id` 可选（关联到触发的 buffer）

**删除的字段**：

- ❌ `content` (JSONB) - 改为简单字段
- ❌ `content_preview` (TEXT) - 不再需要
- ❌ `response_id` (VARCHAR) - 移至 `ai_request_logs`
- ❌ `llm_config_id` (INTEGER) - 移至 `ai_request_logs`

### 2. `ai_conversation_state` 表（新增）

```sql
-- 新增表：ai_conversation_state
CREATE TABLE ai_conversation_state (
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    pending_messages JSONB,
    interrupted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_qiao_id, character_qiao_id)
);

CREATE INDEX idx_conversation_state_updated
ON ai_conversation_state(updated_at);

COMMENT ON TABLE ai_conversation_state IS
  'Stores per-conversation transient state, such as pending messages from an interrupted response.';
COMMENT ON COLUMN ai_conversation_state.pending_messages IS
  'Unsent messages from an interrupted response. Format: {"outgoing": [...], "followup": [...], "total_pending": N}';
COMMENT ON COLUMN ai_conversation_state.interrupted_at IS
  'Timestamp when the sending process was last interrupted.';
```

### 3. `ai_relationships` 表新增字段

```sql
-- 在 ai_relationships 表中添加 followup_delay_ms 字段
ALTER TABLE ai_relationships ADD COLUMN followup_delay_ms INTEGER DEFAULT 5000
    CHECK (followup_delay_ms >= 0);

COMMENT ON COLUMN ai_relationships.followup_delay_ms IS 'Delay between outgoing and followup messages in milliseconds';

-- 更新现有关系的默认值
UPDATE ai_relationships SET followup_delay_ms = CASE name
        WHEN 'romantic' THEN 2000      -- 浪漫关系：快速连发
        WHEN 'intimate' THEN 2500      -- 亲密关系：快速
        WHEN 'warm' THEN 3000          -- 温暖关系：较快
        WHEN 'friendly' THEN 4000      -- 友好关系：正常
        WHEN 'neutral' THEN 5000       -- 中立关系：标准
        WHEN 'cold' THEN 8000          -- 冷淡关系：较慢
        WHEN 'hostile' THEN 12000      -- 敌对关系：很慢
        WHEN 'crushing' THEN 2000      -- 暗恋关系：快速
        ELSE 5000
    END;
```

### 4. `ai_request_logs` 表字段修改

**设计决策**：将 `conversation_item_id` 改为 `buffer_id`，因为一次请求产生多条消息。

```sql
-- 修改后的 ai_request_logs 表
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGINT PRIMARY KEY,
    character_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    style_id INTEGER NOT NULL,
    personality_id INTEGER NOT NULL,
    request_type VARCHAR(20) NOT NULL DEFAULT 'production',
    provider_name VARCHAR(50),
    model_name VARCHAR(100),
    llm_config_id INTEGER,  -- LLM 配置 ID
    response_id VARCHAR(64),  -- Doubao 响应 ID
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    buffer_id BIGINT,  -- 关联到触发的 buffer
    request JSONB NOT NULL,
    response JSONB,
    status INTEGER NOT NULL,
    token_count INTEGER,
    response_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON COLUMN ai_request_logs.buffer_id IS
  'Associated buffer ID that triggered this LLM request.';

CREATE INDEX idx_ai_request_logs_response_id ON ai_request_logs(response_id);
CREATE INDEX idx_ai_request_logs_buffer_id ON ai_request_logs(buffer_id);
```

**关系图**：

```
ai_message_buffer (buffer_id=123)
    ├─→ ai_conversation_items (role=user, buffer_id=123)  -- 用户消息
    ├─→ ai_request_logs (buffer_id=123, response_id=xxx)  -- LLM 请求日志
    └─→ ai_conversation_items (role=assistant, buffer_id=123) × N  -- AI 消息
```

---

## 核心模块

### 1. 用户消息入站（⚠️ 需要修改）

**位置**：`backend/app/services/message/processing/buffer.py`

**⚠️ 变更点**：从 JSONB 内容块改为简单字段存储

**旧代码（需要修改）**：

```python
# ❌ 旧代码：存储 JSONB 内容块
new_item = AIConversationItem(
    user_qiao_id=event.from_qiao_id,
    character_qiao_id=character_qiao_id,
    role="user",
    content=[{"type": "text", "text": event.content}],  # ❌ JSONB 格式
    content_preview=event.content[:100],  # ❌ 不再需要
    client_msg_ids=[event.msg_id],
    buffer_id=buffer_obj.id,
)
```

**新代码（目标实现）**：

```python
# ✅ 新代码：使用简单字段存储
async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """Buffer inbound message with wake mechanism"""

    # 1. 触发打断（如果有正在发送的任务）
    from .sender import interrupt_sending_task
    interrupt_sending_task(event.from_qiao_id, character_qiao_id)

    # 2-4. 检查角色状态、分类消息、获取 buffer（现有逻辑）
    # ...

    # 5. 构建消息内容（新逻辑）
    if event.message_type == MessageType.TEXT:
        message_type = "text"
        text_content = event.content
        media_url = None
        media_metadata = None
    elif event.message_type == MessageType.IMAGE:
        message_type = "image"
        text_content = None
        media_url = event.image_url
        media_metadata = {
            "caption": event.content or None,
            "width": event.image_width,
            "height": event.image_height,
        }
    elif event.message_type == MessageType.AUDIO:
        message_type = "audio"
        text_content = None
        media_url = event.audio_url
        # 语音转文字（未来实现）
        transcript = await transcribe_audio(event.audio_url) if event.audio_url else None
        media_metadata = {
            "duration": event.audio_duration,
            "transcript": transcript,
        }
    else:
        logger.warning(f"Unsupported message type: {event.message_type}")
        return

    # 6. 写入 ai_conversation_items（新字段结构）
    new_item = AIConversationItem(
        user_qiao_id=event.from_qiao_id,
        character_qiao_id=character_qiao_id,
        role="user",
        message_type=message_type,  # ✅ 简单字段
        text_content=text_content,  # ✅ 简单字段
        media_url=media_url,        # ✅ 简单字段
        media_metadata=media_metadata,  # ✅ 简单字段
        client_msg_ids=[event.msg_id],
        buffer_id=buffer_obj.id,
        created_at=datetime.utcnow(),
    )
    db.add(new_item)

    # 7. 更新 buffer 元数据（现有逻辑）
    # ...

    await db.commit()
```

### 2. AI 消息发送（⚠️ 需要修改）

**位置**：`backend/app/services/message/processing/sender.py`

**⚠️ 变更点**：从 JSONB 内容块改为简单字段存储

**旧代码（需要修改）**：

```python
# ❌ 旧代码：存储 JSONB 内容块
new_item = AIConversationItem(
    user_qiao_id=user_qiao_id,
    character_qiao_id=character_qiao_id,
    role="assistant",
    content=[{"type": "text", "text": msg}],  # ❌ JSONB 格式
    buffer_id=buffer_id,
)
```

**新代码（目标实现）**：

```python
# ✅ 新代码：使用简单字段存储
async def _send_message_list(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    buffer_id: int,
    messages: List[str],
    phase: str,
    typing_speed: float,
    interrupt_event: asyncio.Event,
) -> Tuple[bool, int]:
    """Sends a list of messages with typing simulation."""

    for idx, msg in enumerate(messages):
        # 1-3. 打字模拟和打断检查（现有逻辑）
        # ...

        # 4. 发送到 LeanCloud
        await send_message_to_leancloud(
            from_qiao_id=character_qiao_id,
            to_qiao_id=user_qiao_id,
            content=msg,
            message_type="text",
        )

        # 5. 独立插入到数据库（新字段结构）
        new_item = AIConversationItem(
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            role="assistant",
            message_type="text",      # ✅ 简单字段（MVP: 仅文本）
            text_content=msg,         # ✅ 简单字段
            media_url=None,           # ✅ 简单字段
            media_metadata=None,      # ✅ 简单字段
            buffer_id=buffer_id,
            created_at=datetime.utcnow(),
        )
        db.add(new_item)
        await db.commit()

        logger.info("message_sent", phase=phase, index=idx, buffer_id=buffer_id)

    return True, len(messages)
```

**理由**：

- ✅ 保持 `ImmutableSnowflakeModel` 的不可变性契约
- ✅ 完整的审计追踪（每条消息的真实发送时间）
- ✅ 打断场景下逻辑清晰（已发送=已持久化）
- ✅ 并发安全（无需锁机制）
- ✅ LLM 元数据统一记录在 `ai_request_logs`，`ai_conversation_items` 仅保留会话字段

### 3. 查询对话历史（⚠️ 需要修改）

**位置**：`backend/app/services/ai/conversation_flow.py`

**⚠️ 变更点**：从 JSONB 内容块改为简单字段，转换为业务格式

**新代码（目标实现）**：

```python
async def _fetch_conversation_history(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    limit: int = 20,
) -> List[AIConversationItem]:
    """
    Fetch conversation history from database.

    Returns:
        List of conversation items in chronological order (oldest first)
    """
    result = await db.execute(
        select(AIConversationItem)
        .where(
            AIConversationItem.user_qiao_id == user_qiao_id,
            AIConversationItem.character_qiao_id == character_qiao_id,
            AIConversationItem.is_excluded_from_context == False,
        )
        .order_by(AIConversationItem.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return list(reversed(items))  # 按时间正序返回


def _build_business_messages(
    items: List[AIConversationItem]
) -> List[Dict[str, Any]]:
    """
    Convert ORM objects to business format dictionaries.

    Business format (simple dict):
    {
        "role": "user" | "assistant",
        "message_type": "text" | "image" | "audio",
        "text_content": "...",  # for text
        "media_url": "...",     # for image/audio
        "media_metadata": {...} # optional
    }

    Args:
        items: List of AIConversationItem ORM objects

    Returns:
        List of business format dictionaries
    """
    messages = []
    for item in items:
        msg = {
            "role": item.role,
            "message_type": item.message_type,
        }

        if item.message_type == "text":
            msg["text_content"] = item.text_content
        elif item.message_type in ("image", "audio"):
            msg["media_url"] = item.media_url
            if item.media_metadata:
                msg["media_metadata"] = item.media_metadata

        messages.append(msg)

    return messages
```

### 4. LLM 适配层格式转换（⚠️ 需要修改）

**位置**：`backend/app/services/llm/converters/responses_format.py`

**⚠️ 变更点**：从业务格式（简单字段）转换为 Doubao Responses API 格式，并合并连续 role

**新代码（目标实现）**：

```python
class ResponsesFormatConverter(MessageConverter):
    """Convert business format to Doubao Responses API format."""

    def convert_to_provider_format(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert business format to Doubao Responses API format.

        Input (business format):
            {
                "role": "user",
                "message_type": "text",
                "text_content": "Hello"
            }

        Output (Doubao format):
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }

        Note: Merges consecutive messages with the same role to comply with
        Doubao API requirements.
        """
        converted: List[Dict[str, Any]] = []

        for message in messages:
            role = message["role"]
            message_type = message.get("message_type", "text")

            # Convert to provider content blocks
            content_blocks = self._convert_message_to_blocks(message, message_type)

            # Merge with previous message if same role
            if converted and converted[-1]["role"] == role:
                converted[-1]["content"].extend(content_blocks)
            else:
                converted.append({
                    "role": role,
                    "content": content_blocks
                })

        return converted

    def _convert_message_to_blocks(
        self,
        message: Dict[str, Any],
        message_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Convert single message to provider content blocks.

        Args:
            message: Business format message
            message_type: Message type (text/image/audio)

        Returns:
            List of Doubao content blocks
        """
        if message_type == "text":
            return [{
                "type": "input_text",
                "text": message["text_content"]
            }]
        elif message_type == "image":
            return [{
                "type": "input_image",
                "image_url": {"url": message["media_url"]}
            }]
        elif message_type == "audio":
            # 语音转文字后作为文本
            metadata = message.get("media_metadata", {})
            transcript = metadata.get("transcript", "[语音消息]")
            return [{
                "type": "input_text",
                "text": f"[语音消息: {transcript}]"
            }]
        else:
            logger.warning("unknown_message_type", message_type=message_type)
            return [{
                "type": "input_text",
                "text": "[不支持的消息类型]"
            }]
```

**理由**：

- ✅ 职责分离：业务层不需要知道 LLM 格式要求
- ✅ 依赖倒置：如果换其他 LLM，只需修改对应的 Converter
- ✅ 符合 SOLID 原则：每层只做自己该做的事

### 5. 打字时间计算（无需修改）

**配置来源**：`typing_speed_wpm` 存储在 `ai_characters`（角色实例字段，创建时由模板赋值）。运行阶段如果读不到或配置<=0，使用 35 WPM 作为兜底，再换算出 `typing_speed_seconds_per_word = 60 / typing_speed_wpm`。

```python
def calculate_typing_time(message: str, typing_speed: float) -> float:
    """
    Calculates typing time based on message content and typing speed.

    Args:
        message: Message text
        typing_speed: Seconds per word (由 ai_characters.typing_speed_wpm 推导，fallback 35 WPM)

    Returns:
        Typing time in seconds
    """
    word_count = _count_words(message)
    return typing_speed * word_count

def _count_words(text: str) -> int:
    """
    Counts 'words' based on character width:
    - 1 full-width char (CJK) = 1 word
    - 3 half-width chars (ASCII) = 1 word
    - 1 emoji = 1 word
    """
    import unicodedata
    word_count = 0
    half_width_count = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            word_count += 1
        elif unicodedata.category(char).startswith('So'):  # Emoji
            word_count += 1
        else:
            half_width_count += 1

    word_count += (half_width_count + 2) // 3  # Ceiling division
    return max(word_count, 1)
```

---

## 打断机制

### 触发入口

**位置**：`backend/app/services/message/processing/buffer.py` 的 `add_message_to_buffer` 函数入口处。

```python
async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """Buffer inbound message with wake mechanism"""

    # 1. 首先触发打断（如果有正在发送的任务）
    from .sender import interrupt_sending_task
    interrupt_sending_task(event.from_qiao_id, character_qiao_id)

    # 2. 检查角色是否被阻断
    character = await _get_character_status(db, character_qiao_id)
    if character.status == CharacterStatus.BLOCKED:
        logger.info("buffer_rejected_blocked_character", ...)
        return

    # 3. 继续现有的 buffer 逻辑（wake/OPEN/LOCKED）
    category = _categorize_event(event)
    if category is None:
        return

    # ... 现有代码 ...
```

### 打断函数

```python
# backend/app/services/message/processing/sender.py

# Global registry of active sending tasks
_active_sending_tasks: Dict[Tuple[str, str], asyncio.Event] = {}

def interrupt_sending_task(user_qiao_id: str, character_qiao_id: str) -> None:
    """
    Interrupt active sending task for this conversation (same-instance only).

    Called by add_message_to_buffer when a new user message arrives.
    """
    conversation_key = (user_qiao_id, character_qiao_id)
    event = _active_sending_tasks.get(conversation_key)

    if event:
        event.set()  # Signal interruption
        logger.info(
            "sending_task_interrupted",
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
        )
```

### 触发规则

| 场景 | 是否触发打断 | 理由 |
|------|------------|------|
| 用户发送新消息（TEXT/IMAGE/VIDEO） | ✅ 是 | 核心场景，模拟真人被打断 |
| 用户发送 typing_start/typing_end | ✅ 是 | 表示用户正在输入，应停止发送 |
| 管理员操作（block/修改配置） | ❌ 否 | 管理操作不应影响正在进行的对话 |
| 系统内部事件（定时任务等） | ❌ 否 | 仅用户行为触发打断 |

---

## 完整流程

### 数据流示例

```python
# 1. 数据库层：独立存储每条消息（简单字段）
| id | role      | message_type | text_content        | created_at | buffer_id |
|----|-----------|--------------|---------------------|------------|-----------|
| 1  | user      | text         | "你好"              | 10:00:00   | 100       |
| 2  | assistant | text         | "你好！"            | 10:00:05   | 100       |
| 3  | assistant | text         | "有什么可以帮你？"   | 10:00:08   | 100       |
| 4  | user      | text         | "打断"              | 10:00:10   | 101       |
| 5  | assistant | text         | "好的"              | 10:00:15   | 101       |

# 2. 业务层：查询并构建业务格式字典
messages = [
    {"role": "user", "message_type": "text", "text_content": "你好"},
    {"role": "assistant", "message_type": "text", "text_content": "你好！"},
    {"role": "assistant", "message_type": "text", "text_content": "有什么可以帮你？"},
    {"role": "user", "message_type": "text", "text_content": "打断"},
    {"role": "assistant", "message_type": "text", "text_content": "好的"},
]

# 3. LLM 适配层：转换为 Doubao 格式并合并连续 role
converted = converter.convert_to_provider_format(messages)
# 结果：
[
    {"role": "user", "content": [{"type": "input_text", "text": "你好"}]},
    {"role": "assistant", "content": [
        {"type": "input_text", "text": "你好！"},
        {"type": "input_text", "text": "有什么可以帮你？"}
    ]},  # ← 合并了 id=2 和 id=3
    {"role": "user", "content": [{"type": "input_text", "text": "打断"}]},
    {"role": "assistant", "content": [{"type": "input_text", "text": "好的"}]},
]

# 4. 发送给 Doubao API
response = client.responses.create(
    model="doubao-seed-1-6-250615",
    input=converted  # ← 已经合并好的消息
)
```

---

## 配置说明

### 参数来源

| 参数 | 来源 | 说明 |
|------|------|------|
| `typing_speed_wpm` | `ai_characters.typing_speed_wpm` | 角色级别的打字节奏，单位：词/分钟（换算秒/词，缺失时 fallback 35） |
| `followup_delay_ms` | `ai_relationships.followup_delay_ms` | outgoing 与 followup 之间的等待，按关系区分 |
| `pending_messages` | `ai_conversation_state.pending_messages` | 上一轮被打断的内容 |

### 加载示例

```python
async def _get_typing_speed(db: AsyncSession, character_qiao_id: str) -> float:
    """Get typing speed (seconds/word) derived from ai_characters.typing_speed_wpm with 35 WPM fallback."""
    result = await db.execute(
        select(AICharacter.typing_speed_wpm)
        .where(AICharacter.qiao_id == character_qiao_id)
    )
    return result.scalar_one()

async def _get_followup_delay(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str
) -> int:
    """Get followup delay from ai_relationships."""
    relationship_config = await get_character_relationship_config(
        db, character_qiao_id
    )
    return relationship_config['followup_delay_ms']
```

---

## 迁移指南

### ⚠️ 重要：从 JSONB 内容块迁移到简单字段

**影响范围**：

1. 数据库表结构（`ai_conversation_items`）
2. SQLAlchemy 模型（`backend/app/models/ai/character.py`）
3. 消息入站逻辑（`backend/app/services/message/processing/buffer.py`）
4. 消息发送逻辑（`backend/app/services/message/processing/sender.py`）
5. 对话历史查询（`backend/app/services/ai/conversation_flow.py`）
6. LLM 适配层（`backend/app/services/llm/converters/responses_format.py`）

### 迁移步骤

#### 1. 数据库迁移

**文件**：`backend/database/migrations/xxx_migrate_to_simple_fields.sql`

```sql
-- Step 1: 添加新字段
ALTER TABLE ai_conversation_items
ADD COLUMN message_type VARCHAR(20) DEFAULT 'text',
ADD COLUMN text_content TEXT,
ADD COLUMN media_url TEXT,
ADD COLUMN media_metadata JSONB;

-- Step 2: 迁移现有数据（从 content JSONB 提取到简单字段）
UPDATE ai_conversation_items
SET
    message_type = 'text',
    text_content = content->0->>'text'
WHERE content->0->>'type' IN ('text', 'input_text', 'output_text');

-- Step 3: 删除旧字段
ALTER TABLE ai_conversation_items
DROP COLUMN content,
DROP COLUMN content_preview;

-- Step 4: 添加约束
ALTER TABLE ai_conversation_items
ADD CONSTRAINT ck_ai_conversation_items_content CHECK (
    (message_type = 'text' AND text_content IS NOT NULL AND media_url IS NULL)
    OR (message_type IN ('image', 'audio') AND media_url IS NOT NULL)
);

-- Step 5: 修改 buffer_id 约束
ALTER TABLE ai_conversation_items
DROP CONSTRAINT IF EXISTS ck_ai_conversation_items_user_buffer;

ALTER TABLE ai_conversation_items
ADD CONSTRAINT ck_ai_conversation_items_user_buffer CHECK (
    (role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user')
);

-- Step 6: 添加全文搜索索引
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_ai_conv_items_text_search
ON ai_conversation_items USING gin(text_content gin_trgm_ops);

-- Step 7: 更新字段注释
COMMENT ON COLUMN ai_conversation_items.message_type IS 'Message type: text/image/audio';
COMMENT ON COLUMN ai_conversation_items.text_content IS 'Text content (required for message_type=text)';
COMMENT ON COLUMN ai_conversation_items.media_url IS 'Media URL (required for message_type=image/audio)';
COMMENT ON COLUMN ai_conversation_items.media_metadata IS 'Media metadata: {"width": 800, "height": 600} for image, {"duration": 10, "transcript": "..."} for audio';
```

#### 2. SQLAlchemy 模型修改

**文件**：`backend/app/models/ai/character.py`

**需要修改的部分**：

```python
# ❌ 删除这些字段
content: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, ...)
content_preview: Mapped[Optional[str]] = mapped_column(Text, ...)

# ✅ 添加这些字段
message_type: Mapped[str] = mapped_column(
    String(20), nullable=False, default='text',
    server_default=text("'text'"),
    comment="Message type: text/image/audio"
)
text_content: Mapped[Optional[str]] = mapped_column(
    Text, nullable=True,
    comment="Text content (required for message_type='text')"
)
media_url: Mapped[Optional[str]] = mapped_column(
    Text, nullable=True,
    comment="Media URL (required for message_type='image'/'audio')"
)
media_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
    JSONB, nullable=True,
    comment="Media metadata: width/height for image, duration/transcript for audio"
)

# ❌ 修改约束
CheckConstraint(
    "(role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user' AND buffer_id IS NULL)",  # 旧约束
    name="ck_ai_conversation_items_user_buffer",
)

# ✅ 改为
CheckConstraint(
    "(message_type = 'text' AND text_content IS NOT NULL AND media_url IS NULL) "
    "OR (message_type IN ('image', 'audio') AND media_url IS NOT NULL)",
    name="ck_ai_conversation_items_content"
),
CheckConstraint(
    "(role = 'user' AND buffer_id IS NOT NULL) OR (role <> 'user')",  # 新约束
    name="ck_ai_conversation_items_user_buffer",
),
```

#### 3. 代码修改清单

**需要修改的文件**：

1. **`backend/app/services/message/processing/buffer.py`**
   - 修改 `add_message_to_buffer` 函数
   - 从 `content=[{"type": "text", "text": ...}]` 改为 `message_type="text", text_content=...`

2. **`backend/app/services/message/processing/sender.py`**
   - 修改 `_send_message_list` 函数
   - 从 `content=[{"type": "text", "text": msg}]` 改为 `message_type="text", text_content=msg`

3. **`backend/app/services/ai/conversation_flow.py`**
   - 添加 `_build_business_messages` 函数
   - 从 ORM 对象转换为业务格式字典

4. **`backend/app/services/llm/converters/responses_format.py`**
   - 修改 `convert_to_provider_format` 方法
   - 添加 `_convert_message_to_blocks` 方法
   - 从业务格式转换为 Doubao Responses API 格式

### 验证清单

完成迁移后，请验证以下功能：

- [ ] 用户发送文本消息能正常存储
- [ ] AI 回复消息能正常存储
- [ ] 对话历史查询正常
- [ ] LLM 请求格式正确
- [ ] 连续相同 role 的消息能正确合并
- [ ] 打断机制正常工作
- [ ] 全文搜索功能正常

---

## 总结

### 关键设计决策

1. ✅ **使用简单字段存储**：从 JSONB 内容块改为 `message_type` + `text_content` + `media_url`
2. ✅ **依赖倒置**：业务层不依赖 LLM 提供商格式
3. ✅ **取消 buffer 的消息合并逻辑**：用户消息独立插入
4. ✅ **取消发送消息的合并逻辑**：每条消息独立插入
5. ✅ **在 LLM 适配层统一合并**：`ResponsesFormatConverter` 处理连续 role
6. ✅ **保持 `ImmutableSnowflakeModel`**：不可变性契约
7. ✅ **打断触发在 `add_message_to_buffer` 入口**：用户消息到达时立即打断

### 优势

- **数据库层面**：
  - 极致简单（KISS）
  - 查询直观（`WHERE text_content LIKE '%关键词%'`）
  - 完整审计追踪
  - 并发安全
  - 打断逻辑清晰
- **LLM 层面**：
  - 上下文格式正确
  - 不影响理解
  - 换 LLM 提供商无需迁移数据
- **实现层面**：
  - 逻辑简单
  - 职责分离
  - 符合 SOLID 原则
