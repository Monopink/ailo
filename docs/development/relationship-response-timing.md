# 关系驱动的唤醒时间系统

本文档描述如何实现基于关系等级的AI唤醒时间系统，增强拟人化体验。

## 设计目标

- AI的响应速度反映与用户的关系等级
- 支持随机性，避免机械感
- 支持非线性分布（快速倾向/慢速倾向）
- 支持不回复概率（模拟真人可能忽略消息）
- 支持连续对话免等待机制
- 支持等待期间收到新消息的调整算法

## 核心概念

### 唤醒机制 (Wake Mechanism)

模拟真人"看到消息后思考一段时间"的行为：

1. **消息到达** → 检查是否在连续对话窗口内
2. **需要唤醒** → 采样唤醒等待时间，创建 WAITING_WAKEUP buffer
3. **等待期间** → 可能收到新消息，根据调整算法缩短/延长等待时间
4. **唤醒完成** → 转为 OPEN 状态，进入现有 buffer 流程
5. **buffer到期** → 转为 LOCKED 状态，判断是否回复
6. **回复决策** → 根据 no_reply_probability 决定是否调用 LLM

**关键点：**
- 唤醒等待 ≠ 回复等待（唤醒后可能不回复）
- 不回复的判断在唤醒完成后（processor 处理 LOCKED buffer 时）
- 等待期间的调整算法依然生效（模拟真人"看到消息"的过程）

## 数据库设计

### ai_relationships 表字段修改

```sql
-- 重命名现有字段（统一使用 wake_ 前缀）
ALTER TABLE ai_relationships
  RENAME COLUMN response_time_min_ms TO wake_time_min_ms;

ALTER TABLE ai_relationships
  RENAME COLUMN response_time_max_ms TO wake_time_max_ms;

ALTER TABLE ai_relationships
  RENAME COLUMN response_time_bias TO wake_time_bias;

-- 新增字段
ALTER TABLE ai_relationships
  ADD COLUMN wake_window_ms INTEGER DEFAULT 60000
    CHECK (wake_window_ms >= 0),
  ADD COLUMN wake_time_adjustment VARCHAR(20) DEFAULT 'random_half'
    CHECK (wake_time_adjustment <> '');

-- 更新注释
COMMENT ON COLUMN ai_relationships.wake_time_min_ms IS 'Minimum wake wait time (ms), minimum 500ms';
COMMENT ON COLUMN ai_relationships.wake_time_max_ms IS 'Maximum wake wait time (ms), must be >= min';
COMMENT ON COLUMN ai_relationships.wake_time_bias IS 'Sampling bias: balanced/centered/fast/slow/very_fast/very_slow';
COMMENT ON COLUMN ai_relationships.wake_window_ms IS 'Skip wake if last message within this window (ms)';
COMMENT ON COLUMN ai_relationships.wake_time_adjustment IS 'Wait time adjustment when new message arrives';
COMMENT ON COLUMN ai_relationships.no_reply_probability IS 'Probability of not replying after wake (0.00-1.00)';
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `wake_time_min_ms` | INTEGER | 最小唤醒等待时间（毫秒） | 600 |
| `wake_time_max_ms` | INTEGER | 最大唤醒等待时间（毫秒） | 1500 |
| `wake_time_bias` | VARCHAR(20) | 唤醒时间采样倾向 | 'fast' |
| `wake_window_ms` | INTEGER | 连续对话窗口（毫秒），在此时间内跳过唤醒 | 60000 |
| `wake_time_adjustment` | VARCHAR(20) | 收到新消息时的等待时间调整算法 | 'random_half' |
| `no_reply_probability` | DECIMAL(3,2) | 唤醒后不回复概率（0.00-1.00） | 0.05 |

### 唤醒时间倾向说明

| 倾向值 | 说明 | 分布特征 | 适用场景 |
|--------|------|---------|---------||`balanced` | 均衡分布 | 在 [min, max] 内均匀随机 | 中立关系，无特殊偏好 |
| `centered` | 中间集中 | 集中在中间值附近 | 稳定关系，行为可预测 |
| `fast` | 快速倾向 | 更多接近 min 的值 | 积极关系，倾向快速唤醒 |
| `slow` | 慢速倾向 | 更多接近 max 的值 | 消极关系，倾向慢速唤醒 |
| `very_fast` | 极快倾向 | 集中在 min 附近 | 非常积极的关系（如暗恋） |
| `very_slow` | 极慢倾向 | 集中在 max 附近 | 非常消极的关系（如敌对） |

### 等待时间调整算法说明

| 算法值 | 说明 | 算法逻辑 | 适用场景 |
|--------|------|---------|---------|
| `none` | 不调整 | 保持原剩余时间，但结果至少等待 1 秒（1000ms） | 冷淡或需要保留完整等待的关系 |
| `random_half` | 随机减半 | 50% 概率将剩余时间乘以 `随机数(1-50) / 50`（范围 2%-100%），其余 50% 保持不变，结果至少 1 秒 | 默认行为，模拟真人“可能快一点”的随机性 |

**random_half 细节：**

1. 生成 1-100 的随机数。
2. 随机数 ≤50 → 将剩余时间缩短为 `剩余时间 * (随机数 / 50)`，缩短幅度 [2%, 100%]。
3. 随机数 >50 → 保持原剩余时间。
4. 无论是否缩短，最终剩余时间都会 clamp 到 1000ms 及以上。

### ai_message_buffer 表新增字段

```sql
ALTER TABLE ai_message_buffer
  ADD COLUMN wake_expires_at_ms BIGINT,
  ADD COLUMN wake_adjustment_count SMALLINT DEFAULT 0;

COMMENT ON COLUMN ai_message_buffer.wake_expires_at_ms IS 'Wake timer expiration (ms), NULL if already awake or in OPEN state';
COMMENT ON COLUMN ai_message_buffer.wake_adjustment_count IS 'Number of times wake time was adjusted by new messages';
```

### AIMessageBufferState 枚举新增状态

```python
class AIMessageBufferState(IntEnum):
    WAITING_WAKEUP = 0  # 等待唤醒
    OPEN = 1            # 开放（聚合中）
    LOCKED = 2          # 已锁定（处理中）
    COMPLETE = 3        # 已完成
    CANCELLED = 4       # 已取消
```

## 配置示例

```sql
-- 友好关系：快速唤醒（0.6-1.5秒），快速倾向，总是回复，适度加快
UPDATE ai_relationships SET
    wake_time_min_ms = 600,
    wake_time_max_ms = 1500,
    wake_time_bias = 'fast',
    wake_window_ms = 60000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.00
WHERE name = 'friendly';

-- 温暖关系：快速唤醒（0.6-1.5秒），极快倾向，总是回复，激进加快
UPDATE ai_relationships SET
    wake_time_min_ms = 600,
    wake_time_max_ms = 1500,
    wake_time_bias = 'very_fast',
    wake_window_ms = 45000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.00
WHERE name = 'warm';

-- 中立关系：正常唤醒（2.4-3.6秒），均衡分布，偶尔不回复，轻微加快
UPDATE ai_relationships SET
    wake_time_min_ms = 2400,
    wake_time_max_ms = 3600,
    wake_time_bias = 'balanced',
    wake_window_ms = 90000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.03
WHERE name = 'neutral';

-- 冷淡关系：较慢唤醒（4-6秒），慢速倾向，偶尔不回复，不调整
UPDATE ai_relationships SET
    wake_time_min_ms = 4000,
    wake_time_max_ms = 6000,
    wake_time_bias = 'slow',
    wake_window_ms = 120000,
    wake_time_adjustment = 'none',
    no_reply_probability = 0.08
WHERE name = 'cold';

-- 敌对关系：慢速唤醒（6-12秒），极慢倾向，经常不回复，轻微减慢
UPDATE ai_relationships SET
    wake_time_min_ms = 6000,
    wake_time_max_ms = 12000,
    wake_time_bias = 'very_slow',
    wake_window_ms = 180000,
    wake_time_adjustment = 'none',
    no_reply_probability = 0.15
WHERE name = 'hostile';

-- 暗恋关系：快速唤醒（1.2-2.4秒），极快倾向，总是回复，激进加快
UPDATE ai_relationships SET
    wake_time_min_ms = 1200,
    wake_time_max_ms = 2400,
    wake_time_bias = 'very_fast',
    wake_window_ms = 30000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.00
WHERE name = 'crushing';

-- 亲密关系：快速唤醒（1.2-2.4秒），快速倾向，总是回复，激进加快
UPDATE ai_relationships SET
    wake_time_min_ms = 1200,
    wake_time_max_ms = 2400,
    wake_time_bias = 'fast',
    wake_window_ms = 45000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.00
WHERE name = 'intimate';

-- 浪漫关系：快速唤醒（0.9-1.8秒），极快倾向，总是回复，激进加快
UPDATE ai_relationships SET
    wake_time_min_ms = 900,
    wake_time_max_ms = 1800,
    wake_time_bias = 'very_fast',
    wake_window_ms = 30000,
    wake_time_adjustment = 'random_half',
    no_reply_probability = 0.00
WHERE name = 'romantic';
```

## 完整流程

```
消息A到达 (add_message_to_buffer)
│
├─ 查询最近的 COMPLETE buffer
│  └─ 检查 last_msg_time_ms 是否在 wake_window_ms 内
│     ├─ 是 → 跳过唤醒，直接创建 OPEN buffer
│     └─ 否 → 需要唤醒等待
│
├─ 采样唤醒等待时间
│  └─ sampled_time = sample_wake_time(min_ms, max_ms, bias)
│
├─ 创建 WAITING_WAKEUP buffer
│  ├─ wake_expires_at_ms = now_ms + sampled_time
│  └─ wake_adjustment_count = 0
│
├─ 等待期间收到消息B
│  ├─ 根据 wake_time_adjustment 调整 wake_expires_at_ms
│  ├─ wake_adjustment_count += 1
│  └─ 更新 buffer 内容
│
├─ wake_expires_at_ms 到期 (processor 轮询)
│  └─ 转为 OPEN 状态
│
├─ buffer 微计时器/宏计时器到期 (processor 轮询)
│  └─ 转为 LOCKED 状态
│
├─ 处理 LOCKED buffer (processor)
│  ├─ 判断 no_reply_probability
│  │  ├─ random.random() < no_reply_probability
│  │  │  └─ 决定不回复 → 转为 COMPLETE（不调用 LLM）
│  │  └─ 否则
│  │     └─ 决定回复 → 调用 LLM → 转为 COMPLETE
│  │
│  └─ 记录日志
│
└─ 下次收到消息C时，重新开始整个流程
```

## 实现代码

### 1. 采样函数

```python
import random
import math

def sample_wake_time(
    min_ms: int,
    max_ms: int,
    bias: str = 'balanced'
) -> int:
    """Sample wake time based on bias

    Args:
        min_ms: Minimum time (milliseconds)
        max_ms: Maximum time (milliseconds)
        bias: Bias type

    Returns:
        Sampled wake time (milliseconds)
    """
    if min_ms == max_ms:
        return min_ms

    u = random.random()

    if bias == 'balanced':
        ratio = u
    elif bias == 'centered':
        mean = 0.5
        std = 0.15
        u2 = random.random()
        z = math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * u2)
        ratio = mean + std * z
        ratio = max(0, min(1, ratio))
    elif bias == 'fast':
        ratio = u ** 2
    elif bias == 'slow':
        ratio = math.sqrt(u)
    elif bias == 'very_fast':
        ratio = u ** 3
    elif bias == 'very_slow':
        ratio = u ** (1/3)
    else:
        ratio = u

    return int(min_ms + ratio * (max_ms - min_ms))
```

### 2. 等待时间调整函数

```python
def adjust_wake_time(
    current_remaining_ms: int,
    adjustment_mode: str,
    wake_time_min_ms: int,
) -> int:
    """Adjust wake time based on adjustment mode

    Returns:
        Adjusted remaining wait time (spec minimum: 1000ms)
    """
    minimum_ms = 1000
    if current_remaining_ms <= 0:
        return minimum_ms

    if adjustment_mode != 'random_half':
        return max(current_remaining_ms, minimum_ms)

    random_number = random.randint(1, 100)
    if random_number <= 50:
        new_remaining = int(current_remaining_ms * random_number / 50)
    else:
        new_remaining = current_remaining_ms

    return max(new_remaining, minimum_ms)
```

### 3. 检查是否需要唤醒

```python
async def check_needs_wake(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
) -> bool:
    """Check if wake wait is needed

    Returns:
        True if wake is needed, False if can skip (within wake_window)
    """
    # Query latest COMPLETE buffer
    result = await db.execute(
        select(AIMessageBuffer)
        .where(
            AIMessageBuffer.user_qiao_id == user_qiao_id,
            AIMessageBuffer.character_qiao_id == character_qiao_id,
            AIMessageBuffer.aggregate_state == AIMessageBufferState.COMPLETE,
        )
        .order_by(AIMessageBuffer.created_at.desc())
        .limit(1)
    )
    last_buffer = result.scalar_one_or_none()

    if not last_buffer:
        return False  # First conversation, skip wake

    # Get relationship config
    relationship_config = await get_relationship_config(db, character_qiao_id)
    wake_window_ms = relationship_config['wake_window_ms']

    current_time = await get_db_now_ms(db)
    time_since_last = current_time - last_buffer.last_msg_time_ms

    return time_since_last > wake_window_ms
```

### 4. 在 add_message_to_buffer 中集成唤醒逻辑

```python
async def add_message_to_buffer(
    db: AsyncSession,
    event: InboundMessageEvent,
    character_qiao_id: str,
) -> None:
    """Buffer inbound message with wake mechanism"""

    category = _categorize_event(event)
    if category is None:
        return

    buffer_config = await _get_buffer_config(db)
    current_time = await _get_db_now_ms(db)

    buffer_obj, buffer_item = await _get_latest_open_buffer(
        db, event.from_qiao_id, character_qiao_id, for_update=True
    )

    if buffer_obj is None:
        if event.message_type != MessageType.TEXT:
            return

        # Check if wake is needed
        needs_wake = await check_needs_wake(
            db, event.from_qiao_id, character_qiao_id
        )

        if needs_wake:
            await _create_wake_buffer(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                event=event,
                current_time=current_time,
            )
        else:
            await _create_new_buffer_window(
                db=db,
                user_qiao_id=event.from_qiao_id,
                character_qiao_id=character_qiao_id,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )
    else:
        # Handle WAITING_WAKEUP state
        if buffer_obj.aggregate_state == AIMessageBufferState.WAITING_WAKEUP:
            await _handle_wake_adjustment(
                db=db,
                buffer_obj=buffer_obj,
                buffer_item=buffer_item,
                event=event,
                current_time=current_time,
            )
        else:
            await _update_buffer_window(
                db=db,
                buffer_obj=buffer_obj,
                buffer_item=buffer_item,
                event=event,
                category=category,
                config=buffer_config,
                current_time=current_time,
            )

    await db.commit()
```

### 5. 在 processor 中判断 no_reply_probability

```python
async def process_locked_buffer(db: AsyncSession, buffer_id: int):
    """Process locked buffer with no_reply check"""

    buffer_obj, item_obj = await _get_buffer_and_item(
        db, buffer_id, require_locked=True
    )

    if not buffer_obj or not item_obj:
        return

    # Get relationship config
    relationship_config = await get_relationship_config(
        db, buffer_obj.character_qiao_id
    )
    no_reply_prob = relationship_config['no_reply_probability']

    # Check no_reply_probability
    should_reply = random.random() >= no_reply_prob

    if not should_reply:
        # Don't reply: finalize without LLM call
        await finalize_buffer_if_locked(
            db, buffer_id, target_state=AIMessageBufferState.COMPLETE
        )
        logger.info(
            "buffer_no_reply_decision",
            buffer_id=buffer_id,
            no_reply_probability=no_reply_prob,
        )
        return

    # Normal processing: call LLM
    # ... (existing LLM call logic)
```

## 代码组织

所有唤醒相关代码放在 `backend/app/services/message/processing/buffer.py` 中：

```python
# ============================================================================
# Wake mechanism (relationship-driven response timing)
# ============================================================================

async def check_needs_wake(...) -> bool:
    """Check if wake wait is needed"""
    pass

async def create_wake_buffer(...) -> None:
    """Create WAITING_WAKEUP buffer"""
    pass

async def handle_wake_adjustment(...) -> None:
    """Adjust wake time when new message arrives"""
    pass

def sample_wake_time(...) -> int:
    """Sample wake time based on relationship config"""
    pass

def adjust_wake_time(...) -> int:
    """Adjust wake time based on adjustment mode"""
    pass

async def get_relationship_config(...) -> dict:
    """Fetch relationship timing configuration"""
    pass

# ============================================================================
# Existing buffer logic (modified)
# ============================================================================

async def add_message_to_buffer(...):
    """Modified: add wake logic"""
    pass

# ... other existing functions ...
```

## 分布效果示例

假设 min=1000ms, max=5000ms：

| 倾向 | 1000-2000ms | 2000-3000ms | 3000-4000ms | 4000-5000ms | 说明 |
|------|------------|------------|------------|------------|------|
| balanced | 25% | 25% | 25% | 25% | 均匀分布 |
| centered | 16% | 34% | 34% | 16% | 集中在中间 |
| fast | 44% | 31% | 19% | 6% | 偏向快速 |
| slow | 6% | 19% | 31% | 44% | 偏向慢速 |
| very_fast | 58% | 27% | 12% | 3% | 强烈偏向快速 |
| very_slow | 3% | 12% | 27% | 58% | 强烈偏向慢速 |

## 测试建议

### 单元测试

```python
from unittest.mock import patch

def test_sample_wake_time_balanced():
    """Test balanced distribution"""
    samples = [sample_wake_time(1000, 5000, 'balanced') for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert 2800 <= mean <= 3200

def test_sample_wake_time_fast():
    """Test fast bias"""
    samples = [sample_wake_time(1000, 5000, 'fast') for _ in range(1000)]
    mean = sum(samples) / len(samples)
    assert mean < 2500

def test_adjust_wake_time():
    """Test wake time adjustment"""
    with patch("services.message.processing.buffer.random.randint", return_value=20):
        adjusted = adjust_wake_time(5000, 'random_half', 500)
        assert adjusted == 2000

    with patch("services.message.processing.buffer.random.randint", return_value=80):
        adjusted = adjust_wake_time(5000, 'random_half', 500)
        assert adjusted == 5000

    # none mode still enforces the 1s floor
    adjusted_none = adjust_wake_time(300, 'none', 500)
    assert adjusted_none == 1000

def test_no_reply_probability():
    """Test no_reply probability"""
    no_reply_count = sum(
        1 for _ in range(1000)
        if random.random() < 0.10
    )
    assert 70 <= no_reply_count <= 130
```

### 集成测试

1. 创建不同关系等级的测试角色
2. 发送多条消息，记录唤醒时间
3. 验证唤醒时间分布符合配置
4. 验证不回复概率符合配置
5. 验证连续对话窗口机制
6. 验证等待时间调整算法

## 注意事项

1. **最小时间限制**：`wake_time_min_ms >= 500`，避免过快显得不真实
2. **不回复概率上限**：建议不超过 0.20（20%），避免用户体验差
3. **数据库时钟**：所有时间计算使用数据库时钟，确保多实例一致性
4. **日志记录**：记录唤醒事件、调整事件、不回复决策，便于分析和调试
5. **首次对话**：首次对话跳过唤醒等待，直接创建 OPEN buffer
6. **调整下限**：等待时间调整后不低于 `wake_time_min_ms` 的 50%

## 实施细节

### 1. 状态机调整

#### _get_latest_open_buffer 修改

```python
async def _get_latest_open_buffer(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    *,
    for_update: bool = False,
) -> Tuple[Optional[AIMessageBuffer], Optional[AIConversationItem]]:
    """Query latest OPEN or WAITING_WAKEUP buffer"""
    query: Select = (
        select(AIMessageBuffer, AIConversationItem)
        .join(
            AIConversationItem,
            AIConversationItem.buffer_id == AIMessageBuffer.id,
            isouter=True,
        )
        .where(
            AIMessageBuffer.user_qiao_id == user_qiao_id,
            AIMessageBuffer.character_qiao_id == character_qiao_id,
            AIMessageBuffer.aggregate_state.in_([
                AIMessageBufferState.WAITING_WAKEUP,  # 新增
                AIMessageBufferState.OPEN
            ]),
        )
        .order_by(AIMessageBuffer.created_at.desc())
        .limit(1)
    )
    if for_update:
        query = query.with_for_update(skip_locked=True)

    result = await db.execute(query)
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]
```

#### lock_conversation_preemptively 修改

```python
async def lock_conversation_preemptively(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
) -> Optional[int]:
    """Lock expired OPEN buffer (skip WAITING_WAKEUP)"""
    try:
        now_ms = await _get_db_now_ms(db)

        # Cancel all OPEN/LOCKED buffers (not WAITING_WAKEUP)
        await db.execute(
            update(AIMessageBuffer)
            .where(
                AIMessageBuffer.user_qiao_id == user_qiao_id,
                AIMessageBuffer.character_qiao_id == character_qiao_id,
                AIMessageBuffer.aggregate_state.in_(
                    [AIMessageBufferState.OPEN, AIMessageBufferState.LOCKED]
                ),
            )
            .values(aggregate_state=AIMessageBufferState.CANCELLED)
        )

        # Lock expired OPEN buffer only
        result = await db.execute(
            select(AIMessageBuffer)
            .where(
                AIMessageBuffer.user_qiao_id == user_qiao_id,
                AIMessageBuffer.character_qiao_id == character_qiao_id,
                AIMessageBuffer.aggregate_state == AIMessageBufferState.CANCELLED,
                _buffer_expired_clause(now_ms),
            )
            .order_by(AIMessageBuffer.created_at.desc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        buffer_obj = result.scalar_one_or_none()

        if not buffer_obj:
            await db.rollback()
            return None

        buffer_obj.aggregate_state = AIMessageBufferState.LOCKED
        buffer_obj.locked_at = datetime.utcnow()
        buffer_obj.micro_expires_at_ms = None
        buffer_obj.macro_expires_at_ms = None
        await db.flush()
        await db.commit()

        return buffer_obj.id

    except Exception as exc:
        await db.rollback()
        logger.error("buffer_lock_failed", error=str(exc), exc_info=True)
        raise
```

### 2. 后台扫描器设计

#### 扩展现有 scanner.py

现有 scanner.py 已经每 100ms 扫描过期的 OPEN buffers，只需扩展以支持 WAITING_WAKEUP → OPEN 转换和 no_reply 判断。

**修改 1: 在 _scan_and_process 中添加 wake 处理**

```python
async def _scan_and_process() -> None:
    """
    Scan for expired contexts and trigger processing.

    Steps:
    1. Process WAITING_WAKEUP → OPEN transitions
    2. Query expired OPEN contexts (buffer_expires_at_ms <= now)
    3. Group by conversation (user_qiao_id, character_qiao_id)
    4. For each conversation, attempt preemptive lock
    5. If locked successfully, trigger AI processing asynchronously
    """
    async with SessionLocal() as db:
        try:
            now_ms = await _get_db_now_ms(db)

            # Step 1: Process wake-expired buffers (WAITING_WAKEUP → OPEN)
            wake_result = await db.execute(
                update(AIMessageBuffer)
                .where(
                    AIMessageBuffer.aggregate_state == AIMessageBufferState.WAITING_WAKEUP,
                    AIMessageBuffer.wake_expires_at_ms.is_not(None),
                    AIMessageBuffer.wake_expires_at_ms <= now_ms,
                )
                .values(
                    aggregate_state=AIMessageBufferState.OPEN,
                    wake_expires_at_ms=None,
                )
                .execution_options(synchronize_session=False)
            )
            wake_count = wake_result.rowcount or 0
            if wake_count > 0:
                await db.commit()
                logger.info("wake_expired_buffers_transitioned", count=wake_count)

            # Step 2: Query expired OPEN contexts (existing logic)
            result = await db.execute(
                select(
                    AIMessageBuffer.user_qiao_id,
                    AIMessageBuffer.character_qiao_id,
                )
                .where(
                    AIMessageBuffer.aggregate_state == AIMessageBufferState.OPEN,
                    or_(
                        and_(
                            AIMessageBuffer.micro_expires_at_ms.is_not(None),
                            AIMessageBuffer.micro_expires_at_ms <= now_ms,
                        ),
                        and_(
                            AIMessageBuffer.macro_expires_at_ms.is_not(None),
                            AIMessageBuffer.macro_expires_at_ms <= now_ms,
                        ),
                    ),
                )
                .distinct()
            )

            conversations = result.all()

            if not conversations:
                return

            logger.debug(
                "found_expired_contexts",
                count=len(conversations),
                now_ms=now_ms,
            )

            # Step 3-5: Process each conversation (existing logic)
            for user_qiao_id, character_qiao_id in conversations:
                _schedule_processing_task(user_qiao_id, character_qiao_id)

        except Exception as e:
            logger.error("scan_and_process_error", error=str(e), exc_info=True)
```

**修改 2: 在 _process_conversation_async 中添加 no_reply 判断**

```python
async def _process_conversation_async(
    user_qiao_id: str,
    character_qiao_id: str,
) -> None:
    """
    Process a single conversation asynchronously.

    Steps:
    1. Attempt preemptive lock (cancel old + lock new)
    2. If successful, get locked context content
    3. Check no_reply_probability
    4. If should reply, trigger AI processing with buffer_id
    5. Handle errors gracefully (don't crash scanner)
    """
    try:
        async with SessionLocal() as db:
            # Step 1: Attempt preemptive lock
            buffer_id = await lock_conversation_preemptively(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

            if not buffer_id:
                logger.debug(
                    "lock_failed_for_conversation",
                    user_qiao_id=user_qiao_id,
                    character_qiao_id=character_qiao_id,
                )
                return

            # Step 2: Get locked context content
            context = await get_locked_context(db, buffer_id)

            if not context:
                logger.warning(
                    "locked_context_not_found",
                    buffer_id=buffer_id,
                )
                return

            # Step 3: Check no_reply_probability
            from services.ai.queries.character_queries import get_character_relationship_config
            import random

            relationship_config = await get_character_relationship_config(
                db, character_qiao_id
            )
            no_reply_prob = relationship_config.get('no_reply_probability', 0.0)
            should_reply = random.random() >= no_reply_prob

            if not should_reply:
                # Don't reply: finalize without LLM call
                await finalize_buffer_if_locked(
                    db, buffer_id, target_state=AIMessageBufferState.COMPLETE
                )
                logger.info(
                    "buffer_no_reply_decision",
                    buffer_id=buffer_id,
                    no_reply_probability=no_reply_prob,
                )
                return

            logger.info(
                "triggering_ai_processing",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

            # Step 4: Trigger AI processing
            await process_conversation(
                db=db,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
                message_content=context.content,
                message_type="text",
                locked_buffer_id=buffer_id,
                user_message_item_id=context.conversation_item_id,
                message_blocks=context.content_blocks,
                persist=True,
            )

            logger.info(
                "ai_processing_completed",
                buffer_id=buffer_id,
                user_qiao_id=user_qiao_id,
                character_qiao_id=character_qiao_id,
            )

    except Exception as e:
        logger.error(
            "process_conversation_async_error",
            error=str(e),
            user_qiao_id=user_qiao_id,
            character_qiao_id=character_qiao_id,
            exc_info=True,
        )
```

#### 索引优化

```sql
-- 新增索引：扫描 WAITING_WAKEUP 状态的过期 buffer
CREATE INDEX idx_ai_message_buffer_wake_scan
ON ai_message_buffer(wake_expires_at_ms)
WHERE aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL;

-- 现有索引已覆盖 OPEN 状态的 micro/macro 扫描
-- idx_ai_message_buffer_micro (已存在)
-- idx_ai_message_buffer_macro (已存在)
```

### 3. no_reply_probability 注入点

**方案：在 scanner.py 的 _process_conversation_async 中注入**

- **不包装** `process_conversation`（保持其纯粹性）
- **不新增** `process_locked_buffer` 函数到 buffer.py（避免循环依赖）
- **在 scanner 中**直接实现 no_reply 判断逻辑（如上述代码所示）

**理由：**
1. `process_conversation` 是通用的 LLM 调用入口，不应耦合 buffer 特定逻辑
2. no_reply 判断属于 buffer 处理流程的一部分，应在 scanner 中实现
3. 避免 `buffer.py` 依赖 `conversation_flow.py` 造成循环依赖

### 4. get_character_relationship_config 函数

**位置：** `backend/app/services/ai/queries/character_queries.py`

**函数签名：**

```python
async def get_character_relationship_config(
    db: AsyncSession,
    character_qiao_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get relationship timing configuration for a character.

    Fallback strategy:
    1. If character.relationship_id is NULL → return None (first conversation, skip wake)
    2. If relationship data exists and valid → return relationship config
    3. If relationship data invalid (not found/disabled) → return hardcoded defaults with warning log

    Hardcoded defaults (used when relationship data is invalid):
    - wake_time_min_ms: 2000
    - wake_time_max_ms: 4000
    - wake_time_bias: 'balanced'
    - wake_window_ms: 60000
    - wake_time_adjustment: 'random_half'
    - no_reply_probability: 0.0

    Args:
        db: Database session
        character_qiao_id: Character external ID

    Returns:
        None if first conversation (skip wake), otherwise dict with timing config
    """
    # Implementation: Query character's relationship_id and return config or None
    pass
```

### 4. 数据库迁移完整步骤

#### 步骤 1: 创建迁移脚本

```sql
-- backend/database/migrations/001_add_wake_mechanism.sql

-- Step 1: Rename existing columns
ALTER TABLE ai_relationships
  RENAME COLUMN response_time_min_ms TO wake_time_min_ms;

ALTER TABLE ai_relationships
  RENAME COLUMN response_time_max_ms TO wake_time_max_ms;

ALTER TABLE ai_relationships
  RENAME COLUMN response_time_bias TO wake_time_bias;

-- Step 2: Add new columns to ai_relationships
ALTER TABLE ai_relationships
  ADD COLUMN wake_window_ms INTEGER DEFAULT 60000
    CHECK (wake_window_ms >= 0),
  ADD COLUMN wake_time_adjustment VARCHAR(20) DEFAULT 'random_half'
    CHECK (wake_time_adjustment <> '');

-- Step 3: Update column comments
COMMENT ON COLUMN ai_relationships.wake_time_min_ms IS 'Minimum wake wait time (ms), minimum 500ms';
COMMENT ON COLUMN ai_relationships.wake_time_max_ms IS 'Maximum wake wait time (ms), must be >= min';
COMMENT ON COLUMN ai_relationships.wake_time_bias IS 'Sampling bias: balanced/centered/fast/slow/very_fast/very_slow';
COMMENT ON COLUMN ai_relationships.wake_window_ms IS 'Skip wake if last message within this window (ms)';
COMMENT ON COLUMN ai_relationships.wake_time_adjustment IS 'Wait time adjustment when new message arrives';
COMMENT ON COLUMN ai_relationships.no_reply_probability IS 'Probability of not replying after wake (0.00-1.00)';

-- Step 4: Add new columns to ai_message_buffer
ALTER TABLE ai_message_buffer
  ADD COLUMN wake_expires_at_ms BIGINT,
  ADD COLUMN wake_adjustment_count SMALLINT DEFAULT 0;

COMMENT ON COLUMN ai_message_buffer.wake_expires_at_ms IS 'Wake timer expiration (ms), NULL if already awake or in OPEN state';
COMMENT ON COLUMN ai_message_buffer.wake_adjustment_count IS 'Number of times wake time was adjusted by new messages';

-- Step 5: Create new index for wake scanning
CREATE INDEX idx_ai_message_buffer_wake_scan
ON ai_message_buffer(wake_expires_at_ms)
WHERE aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL;

-- Step 6: Update existing relationship default values
UPDATE ai_relationships SET
    wake_window_ms = 60000,
    wake_time_adjustment = 'none'
WHERE wake_window_ms IS NULL OR wake_time_adjustment IS NULL;
```

#### 步骤 2: 更新枚举定义

```python
# backend/app/enums/common.py

class AIMessageBufferState(IntEnum):
    WAITING_WAKEUP = 0  # 新增：等待唤醒
    OPEN = 1            # 开放（聚合中）
    LOCKED = 2          # 已锁定（处理中）
    COMPLETE = 3        # 已完成
    CANCELLED = 4       # 已取消
```

#### 步骤 3: 更新约束检查

```sql
-- 确保 wake_expires_at_ms 只在 WAITING_WAKEUP 状态下非空
ALTER TABLE ai_message_buffer
  ADD CONSTRAINT ck_wake_expires_state CHECK (
    (aggregate_state = 0 AND wake_expires_at_ms IS NOT NULL) OR
    (aggregate_state != 0 AND wake_expires_at_ms IS NULL)
  );
```

## 迁移步骤

1. **数据库迁移**
   - 执行 `001_add_wake_mechanism.sql` 迁移脚本
   - 验证字段重命名和新增字段
   - 验证索引创建成功

2. **代码更新**
   - 更新 `AIMessageBufferState` 枚举，添加 `WAITING_WAKEUP = 0`
   - 在 `buffer.py` 中实现唤醒相关函数（6个函数）
   - 修改 `add_message_to_buffer` 函数，集成唤醒逻辑
   - 修改 `_get_latest_open_buffer` 函数，支持 WAITING_WAKEUP 状态
   - 修改 `lock_conversation_preemptively` 函数，跳过 WAITING_WAKEUP 状态

3. **扩展 Scanner**
   - 修改 `scanner.py` 的 `_scan_and_process` 函数，添加 wake 处理逻辑
   - 修改 `scanner.py` 的 `_process_conversation_async` 函数，添加 no_reply 判断
   - 在 `services/ai/queries/character_queries.py` 中实现 `get_character_relationship_config` 函数

4. **配置默认值**
   - 为现有关系配置 `wake_window_ms` 和 `wake_time_adjustment`
   - 参考"配置示例"章节设置各关系的参数

5. **测试验证**
   - 单元测试：测试采样函数、调整函数
   - 集成测试：测试完整唤醒流程
   - 压力测试：测试 scanner 并发处理能力

6. **部署上线**
   - 灰度发布：先在测试环境验证
   - 监控日志：关注 wake_expired_buffers_transitioned、buffer_no_reply_decision 等日志
   - 性能监控：关注 scanner 处理延迟、数据库查询性能

7. **管理后台配置**
   - 在管理后台添加唤醒参数配置界面
   - 调整各关系的唤醒参数
   - 监控用户反馈，优化参数

8. **持续优化**
   - 分析日志数据，调整默认参数
   - 根据用户反馈优化算法
   - 监控系统性能，优化索引

## 实施状态（2025-11-30）

- **数据库**：`backend/database/migrations/20251130_add_wake_mechanism.sql` 已落地，`backend/database/init/01_schema.sql` 同步更新；包含字段重命名、唤醒窗口/调整字段、`wake_expires_at_ms` 及索引/约束。
- **模型与枚举**：`backend/app/enums/common.py` 新增 `WAITING_WAKEUP`，`backend/app/models/ai/style.py` / `backend/app/models/ai/character.py` 反映全部 wake 字段与索引。
- **Buffer 逻辑**：`backend/app/services/message/processing/buffer.py#L84-L520` 实现 `_check_needs_wake`、`_create_wake_buffer`、`_handle_wake_adjustment`、`sample_wake_time`、`adjust_wake_time` 等函数，并在 `add_message_to_buffer` 中接入关系配置。
- **Scanner**：`backend/app/services/message/processing/scanner.py#L105-L250` 现在会处理 `wake_expired_buffers_transitioned` 日志与 `buffer_no_reply_decision`，并在 `_process_conversation_async` 中执行 no-reply 判定。
- **关系配置查询**：`backend/app/services/ai/queries/character_queries.py#L215-L280` 新增 `get_character_relationship_config`，实现三层回退逻辑并提供硬编码默认值。
- **测试**：`backend/tests/unit/services/message/test_buffer.py#L179-L196` 覆盖 wake 采样/调整，`backend/tests/unit/services/test_character_queries.py#L17-L64` 验证关系配置回退。受限于当前环境未安装 pytest（运行 `pytest` 提示 command not found），需要在线下环境执行 `cd backend && pytest tests/unit/services/test_character_queries.py tests/unit/services/message/test_buffer.py -k wake`。

## 未来扩展

- 支持更多分布类型（如正态分布）
- 支持时间段配置（如晚上唤醒更慢）
- 支持用户级别的个性化调整
- 支持更多调整算法（如指数衰减）
- 支持动态调整 worker 参数（poll_interval, batch_size）

---

## 纠正和补充（2025-11-14）

### wake_time_adjustment 算法纠正

**问题：** 文档中定义的 `faster_gentle`、`faster_moderate`、`faster_aggressive`、`slower_gentle`、`slower_moderate` 等调整算法与实际使用的算法不符。

**实际算法：** 应使用现有代码中的随机调整算法（来自 `_waiting_wakeup_timer` 函数）：

```python
# 生成 1-100 的随机数
random_number = random.randint(1, 100)

# 50% 概率调整等待时间，50% 概率保持不变
if random_number <= 50:
    current_wakeup_secs = max(int(current_wakeup_secs * random_number / 50), 1)
```

**算法说明：**
- 生成 1-100 的随机数
- 如果 ≤50：等待时间调整为 `原时间 * (random_number / 50)`，调整范围 [2%, 100%]
- 如果 >50：保持原等待时间不变
- 最小保证 1 秒

**修正后的 wake_time_adjustment 枚举值：**

| 算法值 | 说明 | 算法逻辑 | 适用场景 |
|--------|------|---------|---------|
| `none` | 不调整 | 保持原等待时间不变 | 冷淡关系，忽略新消息 |
| `random_half` | 随机减半 | 50%概率调整为 `原时间 * (1-100随机数/50)`，50%概率不变 | 所有关系的默认行为，模拟真人随机反应 |

**数据库约束修正：**

```sql
-- 约束已简化为非空检查，不再限制具体枚举值
-- 新增算法时无需修改数据库约束，只需在应用层验证

-- 更新默认值
ALTER TABLE ai_relationships
  ALTER COLUMN wake_time_adjustment SET DEFAULT 'random_half';
```

**配置示例修正：**

所有关系的 `wake_time_adjustment` 应设置为 `'random_half'` 或 `'none'`，删除之前文档中的 `faster_moderate`、`faster_aggressive` 等无效值。

### get_character_relationship_config 回退策略补充

**补充说明：** 当 `character.relationship_id` 为 NULL 时，表示初次对话，应返回 `None` 跳过唤醒等待，而不是使用默认配置。

**回退逻辑：**
1. `character.relationship_id` 为 NULL → 返回 `None`（初次对话，跳过唤醒）
2. `relationship` 数据存在且有效 → 返回真实配置
3. `relationship` 数据无效（不存在/被禁用）→  返回硬编码默认值 + 警告日志

**硬编码默认值：**
```python
{
    'wake_time_min_ms': 2000,
    'wake_time_max_ms': 4000,
    'wake_time_bias': 'balanced',
    'wake_window_ms': 60000,
    'wake_time_adjustment': 'random_half',
    'no_reply_probability': 0.0
}
```
