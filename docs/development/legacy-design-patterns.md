# 旧代码优秀设计参考文档

本文档记录旧代码实现中值得保留和学习的产品体验设计，供日后设计和开发参考。

## 概述

旧代码虽然在架构层面存在问题（内存状态管理、无法真正抢占LLM调用、故障恢复差），但在**产品体验设计**上有许多优秀的细节，这些设计增强了AI对话的拟人化和真实感。

## 1. 细粒度的消息类型系统

### 设计描述

区分多种消息类型，根据客户端能力和用户行为动态调整等待时间：

- `CHAT`: 支持 typing indicator 的普通消息（3秒等待）
- `CHAT_NOTYPING`: 不支持 typing indicator 的普通消息（8秒等待）
- `TYPING`: 用户正在输入
- `TYPING_END`: 用户停止输入（3秒等待）

### 优点

- 根据客户端能力自适应调整响应策略
- 支持 typing indicator 提供更自然的对话节奏
- 区分不同场景的等待时间，平衡响应速度与消息聚合

### 实现参考

```python
# 消息类型枚举
class MessageType(Enum):
    CHAT = "chat"                    # 支持typing的普通消息
    CHAT_NOTYPING = "chat_notyping"  # 不支持typing的普通消息
    TYPING = "typing"                # 用户正在输入
    TYPING_END = "typing_end"        # 用户停止输入

# 等待时间配置
request_secs = {
    MessageType.CHAT: 3,
    MessageType.CHAT_NOTYPING: 8,
    MessageType.TYPING: {"total": 32, "short": 16},
    MessageType.TYPING_END: 3,
}
```

### 应用到新方案

在新方案的 `add_message_to_buffer` 中：

```python
# 根据消息类型确定等待时间
if message_type == 'CONTENT_TYPING':
    wait_ms = get_config('message_buffer_normal_wait_ms')  # 3000
elif message_type == 'CONTENT_NO_TYPING':
    wait_ms = get_config('message_buffer_no_typing_wait_ms')  # 8000
elif message_type == 'typing_end':
    wait_ms = get_config('message_buffer_typing_end_wait_ms')  # 3000
```

## 2. 双计时器机制（微观+宏观）

### 设计描述

使用两个独立的计时器平衡响应速度与消息聚合：

- **微计时器（short）**: 每条新消息重置，快速响应（3-8秒）
- **宏计时器（total）**: 从 typing_start 开始计时，防止无限等待（32秒上限）
- **触发条件**: 任一计时器到期即触发处理

### 优点

- 微计时器保证快速响应用户消息
- 宏计时器防止用户持续输入导致永不触发
- 两者结合提供最佳的用户体验

### 实现参考

```python
# 双计时器配置
request_secs = {
    MessageType.TYPING: {
        "total": 32,   # 宏计时器：32秒绝对上限
        "short": 16    # 微计时器：16秒快速响应
    }
}

# 状态转换示例
if last_message_type == MessageType.CHAT and message_type == MessageType.TYPING:
    # 取消微计时器，设置宏计时器
    _reset_request_timer(
        None,  # 不影响主计时器
        request_secs[MessageType.TYPING]["short"],   # 设置短计时器
        request_secs[MessageType.TYPING]["total"]    # 调整主计时器为总时长
    )
```

### 应用到新方案

已在新方案中实现，使用 `micro_expires_at_ms` 和 `macro_expires_at_ms` 字段。详见 [ai-message-processing.md](ai-message-processing.md#双计时器机制)。

## 3. 关系驱动的响应时间

### 设计描述

AI的回复速度反映与用户的关系等级，增强拟人化体验：

```python
to_wakeup_secs = {
    RelationshipType.FRIEND.value: {
        FriendLevel.HOSTILE.value: 120,    # 敌对：2分钟才回复
        FriendLevel.COLD.value: 100,       # 冷淡：100秒
        FriendLevel.NEUTRAL.value: 50,     # 中立：50秒
        FriendLevel.FRIENDLY.value: 10,    # 友好：10秒
        FriendLevel.WARM.value: 10,        # 温暖：10秒
        "default": 50,
    },
    RelationshipType.ROMANCE.value: {
        RomanceLevel.CRUSHING.value: 20,   # 暗恋：20秒
        RomanceLevel.INTIMATE.value: 20,   # 亲密：20秒
        RomanceLevel.ROMANTIC.value: 15,   # 浪漫：15秒
        "default": 20,
    },
    "default": 50,
}
```

### 优点

- 回复速度成为关系状态的外在表现
- 增强角色的真实感和情感表达
- 符合产品定位："真人对话的节奏、语气、情感"

### 实现参考

```python
# 获取基于关系的等待时间
relationship_map = to_wakeup_secs.get(
    relationship_type,
    to_wakeup_secs["default"]
)
current_wakeup_secs = relationship_map.get(
    relationship_level,
    relationship_map["default"]
)

# 添加随机性增加真实感
random_number = random.randint(1, 100)
if random_number <= 50:
    current_wakeup_secs = max(int(current_wakeup_secs * random_number / 50), 1)

# 5% 概率不回复（模拟真人可能忽略消息）
if random_number <= 5:
    to_wakeup = False
```

### 应用到新方案

在计算 `micro_expires_at_ms` 时应用关系系数：

```python
def calculate_buffer_expiry(
    base_wait_ms: int,
    friend_level: str,
    romance_level: str,
    relationship_type: str
) -> int:
    """计算考虑关系等级的到期时间"""

    # 获取关系系数（1.0 = 标准速度，>1.0 = 更慢，<1.0 = 更快）
    multiplier = get_relationship_multiplier(
        relationship_type,
        friend_level,
        romance_level
    )

    # 应用系数
    adjusted_wait_ms = int(base_wait_ms * multiplier)

    return now_ms + adjusted_wait_ms
```

**配置示例**（存储在 `system_configs` 或数据库表）：

```json
{
  "relationship_wait_multipliers": {
    "friend": {
      "hostile": 2.4,    // 120秒 / 50秒基准
      "cold": 2.0,
      "neutral": 1.0,
      "friendly": 0.2,
      "warm": 0.2
    },
    "romance": {
      "crushing": 0.4,
      "intimate": 0.4,
      "romantic": 0.3
    }
  }
}
```

## 4. 中断处理与状态保存

### 设计描述

当AI正在发送多条消息时被用户新消息中断，系统能够：

1. 区分消息状态：`PENDING`（待发送）、`SENDING`（发送中）、`SENT`（已发送）
2. 保存已发送的消息到上下文
3. 丢弃未发送的消息
4. 将未发送的内容保存到 `unsent_message` 字段供下次参考

### 优点

- 避免将"未发送的消息"写入对话历史，保持上下文准确性
- 保留未发送内容供AI参考，增强连贯性
- 模拟真人被打断的行为

### 实现参考

```python
async def _handle_interrupted_reply(self):
    """处理被中断的回复"""
    async with self.typing_queue_lock:
        # 重建已发送和未发送的消息
        sent_messages = [
            msg["content"]
            for msg in self.typing_queue["reply_messages"]
            if msg["status"] == TypingStatus.SENT.value
        ]
        unsent_messages = [
            msg["content"]
            for msg in self.typing_queue["reply_messages"]
            if msg["status"] != TypingStatus.SENT.value
        ]

        # 保存未发送的内容
        if unsent_messages:
            self.unsent_message = self.message_tag.join(unsent_messages)

        # 只将已发送的消息写入上下文
        if sent_messages:
            self._append_response_to_context({
                "reply_content": self.message_tag.join(sent_messages)
            })
```

### 应用到新方案

在新方案中，当检测到新窗口抢占时：

1. 立即中止 Doubao 流式读取
2. 检查哪些消息已通过 LeanCloud 发送
3. 只将已发送的消息写入 `ai_contexts`
4. 将未发送的内容保存到 `ai_characters.unsent_message` 字段
5. 下次构建上下文时，在 system prompt 中包含：`[上次被打断，未发送的内容：{unsent_message}]`

## 5. Typing 模拟系统

### 设计描述

模拟真人打字的行为，增强拟人化体验：

- **打字速度**: 基于字符数计算延迟（`typing_speed * 词数`）
- **词数计算**: `1词数 = 1全角字符 = 3半角字符 = 1emoji = 1特殊字符`
- **随机延迟**: 在发送 `followup_messages` 前添加随机等待（4-16秒）

### 优点

- 模拟真人打字速度，避免"秒回"的机器感
- 随机延迟增加不可预测性，更真实
- 符合产品定位："拟人化和真实感"

### 实现参考

```python
# 配置
typing_speed = 0.6  # 每词0.6秒
prepared_wait_min = 4.0
prepared_wait_max = 16.0

# 计算打字时间
def calculate_typing_time(message: str) -> float:
    """计算打字时间"""
    word_count = 0
    for char in message:
        if is_fullwidth(char) or is_emoji(char):
            word_count += 1
        elif is_halfwidth(char):
            word_count += 1/3

    return typing_speed * word_count

# 发送消息流程
async def send_messages(reply_messages, followup_messages):
    # 发送即时回复
    for msg in reply_messages:
        typing_time = calculate_typing_time(msg)
        await asyncio.sleep(typing_time)
        await send_to_leancloud(msg)

    # 随机等待后发送备发消息
    if followup_messages:
        wait_time = random.uniform(prepared_wait_min, prepared_wait_max)
        await asyncio.sleep(wait_time)

        for msg in followup_messages:
            typing_time = calculate_typing_time(msg)
            await asyncio.sleep(typing_time)
            await send_to_leancloud(msg)
```

### 应用到新方案

在新方案的消息发送阶段（Worker 处理完成后）：

```python
async def send_ai_response(
    outgoing_messages: list[str],
    followup_messages: list[str],
    typing_speed: float
):
    """发送AI回复，模拟打字"""

    # 发送 outgoing_messages
    for msg in outgoing_messages:
        typing_delay = calculate_typing_time(msg, typing_speed)
        await asyncio.sleep(typing_delay)
        await send_message(msg)

    # 等待后发送 followup_messages
    if followup_messages:
        wait_secs = random.uniform(4.0, 16.0)
        await asyncio.sleep(wait_secs)

        for msg in followup_messages:
            typing_delay = calculate_typing_time(msg, typing_speed)
            await asyncio.sleep(typing_delay)
            await send_message(msg)
```

**配置位置**: `ai_personalities.typing_speed` 字段

## 6. 配置驱动的设计

### 设计描述

所有魔法数字和行为参数都通过配置管理，便于调整和A/B测试：

```python
# === TIMER CONFIGS ===
to_wakeup_secs = {...}
to_sleep_secs = 120
request_secs = {...}

# === RELATIONSHIP CONFIGS ===
passive_score_config = {...}
emotion_calculation_rules = {...}
friend_passive_ratio = 0.4
romance_passive_ratio = 0.3

# === CONTEXT CONFIGS ===
memory_limit = 2000
context_limit = 9000
context_expire_num = 12
context_expire_hours = 10

# === LLM CONFIGS ===
llm_params_config = {...}
llm_max_retries = 1
llm_retry_delay_secs = 2

# === REPLY CONFIGS ===
typing_speed = 0.6
prepared_wait_min = 4.0
prepared_wait_max = 16.0
```

### 优点

- 清晰的配置分类（计时器、关系、上下文、LLM、回复）
- 易于调整参数进行优化
- 支持A/B测试不同配置
- 避免硬编码，提高可维护性

### 应用到新方案

**配置存储策略**：

1. **环境变量**（不变更、需要安全的配置）：
   - 数据库连接
   - API密钥
   - 服务端口

2. **`system_configs` 表**（可动态调整的配置）：
   - `message_buffer_normal_wait_ms`: 3000
   - `message_buffer_no_typing_wait_ms`: 8000
   - `message_buffer_typing_total_wait_ms`: 32000
   - `message_buffer_typing_end_wait_ms`: 3000
   - `context_memory_limit`: 2000
   - `context_limit`: 9000
   - `llm_max_retries`: 1
   - `llm_retry_delay_secs`: 2

3. **数据库表字段**（角色级配置）：
   - `ai_personalities.typing_speed`: 0.6
   - `ai_characters.relationship_wait_multiplier`: JSON

**配置读取示例**：

```python
async def get_config(key: str, default=None):
    """从 system_configs 表读取配置"""
    config = await db.fetchval(
        "SELECT value FROM system_configs WHERE key = $1",
        key
    )
    return config if config is not None else default

# 使用
wait_ms = await get_config('message_buffer_normal_wait_ms', 3000)
```

## 7. 情绪衰减系统

### 设计描述

模拟情绪随时间自然衰减，增强角色的动态性：

```python
emotion_calculation_rules = {
    "anger": {
        # 不同愤怒等级的衰减比率
        "decay_ratios": {1: 0.5, 2: 0.4, 3: 0.2},
        # 持续时间倍数（分钟）
        "duration_multipliers": {1: 10, 2: 180, 3: 840},
        # 分数倍数
        "score_multipliers": {1: 2, 2: 2, 3: 10},
        # 随机因子范围（±10%）
        "duration_random_range": (0.9, 1.1),
    },
}
```

### 优点

- 情绪不是永久的，会随时间衰减
- 不同强度的情绪有不同的衰减速度
- 添加随机性，避免机械感

### 应用到新方案

虽然新方案暂不实现情绪系统，但设计思路值得参考：

- 使用时间衰减函数而非固定值
- 不同强度有不同的持续时间
- 添加随机因子增加真实感

## 总结

旧代码在产品体验设计上的优秀实践：

| 设计 | 核心价值 | 新方案状态 |
|------|---------|-----------|
| 细粒度消息类型 | 自适应响应策略 | ✅ 已整合 |
| 双计时器机制 | 平衡速度与聚合 | ✅ 已实现 |
| 关系驱动响应时间 | 增强拟人化 | ⚠️ 待实现 |
| 中断状态保存 | 保持上下文准确 | ⚠️ 待实现 |
| Typing模拟 | 真实感 | ⚠️ 待实现 |
| 配置驱动 | 易于调整优化 | ⚠️ 部分实现 |
| 情绪衰减 | 动态角色 | ❌ 未计划（参考） |

**建议优先级**：

1. **高优先级**（MVP必需）：
   - 关系驱动响应时间
   - Typing模拟
   - 配置驱动设计

2. **中优先级**（增强体验）：
   - 中断状态保存（`unsent_message`）

3. **低优先级**（后续迭代）：
   - 情绪衰减系统

这些设计应该在保持新方案架构优势（数据库状态机、可抢占、故障恢复）的基础上整合，实现既有正确的架构，又有优秀的用户体验。
