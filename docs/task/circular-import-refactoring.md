# 循环导入重构方案

## 文档状态

- **创建日期**: 2025-01-26
- **状态**: 待实施
- **优先级**: 高
- **预计工时**: 4-6小时

## 问题描述

### 现象

`backend/app/services/ai/` 模块中存在大量函数内部的局部 import，违反 PEP 8 规范：

```python
# backend/app/services/ai/queries/transactions.py:138-139
if new_scores:
    from .relationship_queries import get_instance_relationship_scores
    from ..relationship_scoring import determine_relationship_type
```

这些局部 import 分布在以下文件中：
- `conversation_flow.py` (4处)
- `conversation_prompt.py` (4处)
- `queries/transactions.py` (5处)
- `conversation_memory.py` (3处)
- `instance_creation.py` (1处)

### 根本原因

**循环依赖导致的架构问题**：

```
循环1: transactions.py ⇄ relationship_scoring.py
  queries/transactions.py (line 138-139)
    → imports relationship_scoring.determine_relationship_type
  relationship_scoring.py (line 12-16)
    → imports queries/__init__.py
  queries/__init__.py (line 51)
    → imports transactions.py

循环2: transactions.py ⇄ conversation_memory.py
  queries/transactions.py (line 152)
    → imports conversation_memory.process_memory_operations
  conversation_memory.py (line 11-13)
    → imports queries/__init__.py
  queries/__init__.py
    → imports transactions.py

循环3: conversation_flow.py ⇄ queries/transactions.py
  conversation_flow.py (line 378-379)
    → imports queries.transactions.process_llm_response
  queries/transactions.py (line 138-139, 152)
    → imports relationship_scoring, conversation_memory
  relationship_scoring.py, conversation_memory.py
    → imports queries (包含 transactions)
```

**架构违规**：
- `queries/` 目录应该是纯数据访问层，但 `transactions.py` 中的 `process_llm_response` 函数调用了业务逻辑层（relationship_scoring, conversation_memory）
- 违反了**依赖倒置原则**：底层模块（queries）依赖了高层模块（业务逻辑）

## 解决方案

### 架构调整

引入新的 **orchestrators 层**，建立清晰的分层架构：

```
┌─────────────────────────────────────┐
│   API Layer                         │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Orchestration Layer (NEW)        │  ← 协调业务流程
│   orchestrators/                    │
│   - llm_response_handler.py        │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Business Logic Layer              │  ← 纯业务逻辑
│   - relationship_scoring.py         │
│   - conversation_memory.py          │
│   - conversation_prompt.py          │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Data Access Layer                 │  ← 纯数据库操作
│   queries/                          │
│   - transactions.py                 │
│   - instance_queries.py             │
│   - relationship_queries.py         │
└─────────────────────────────────────┘
```

**依赖规则**：
- ✅ 上层可以依赖下层
- ❌ 下层**禁止**依赖上层
- ✅ 同层之间可以依赖（避免循环）

### 重构内容

#### 1. 创建 orchestrators 层

**新建文件**：`backend/app/services/ai/orchestrators/llm_response_handler.py`

**职责**：
- 协调 LLM 响应处理的完整流程
- 调用业务逻辑层（relationship_scoring, conversation_memory）
- 调用数据访问层（queries.transactions）
- 启动异步任务（message sending）

**迁移内容**：
- 从 `queries/transactions.py` 移动 `process_llm_response` 函数到此文件
- 将所有局部 import 改为顶部 import

#### 2. 清理 queries/transactions.py

**保留内容**（纯数据库操作）：
- `create_instance_with_relations()`
- `archive_contexts_transaction()`
- `archive_all_conversation_items()`
- `save_ai_request_log()` - 从 `_save_ai_request_log` 提取为公开函数

**移除内容**：
- `process_llm_response()` - 移到 orchestrators/llm_response_handler.py
- 所有业务逻辑层的 import（relationship_scoring, conversation_memory）

#### 3. 更新导入路径

**需要修改的文件**：
- `backend/app/services/ai/conversation_flow.py`

**修改内容**：
```python
# 原代码 (line 378-379)
from core.database import SessionLocal
from .queries.transactions import process_llm_response

# 修改为
from core.database import SessionLocal
from .orchestrators.llm_response_handler import process_llm_response
```

## 实施步骤

### 前置准备

```bash
# 1. 创建功能分支
git checkout -b refactor/remove-circular-imports

# 2. 确保当前测试通过
cd backend
pytest tests/services/ai/ -v

# 3. 确保容器运行正常
cd ../deployment
docker-compose ps
```

### 步骤1: 创建 orchestrators 目录结构

```bash
cd backend/app/services/ai
mkdir orchestrators
touch orchestrators/__init__.py
touch orchestrators/llm_response_handler.py
```

**文件内容**：

`orchestrators/__init__.py`:
```python
"""
Orchestration layer for AI services.

This layer coordinates between business logic and data access layers.
Orchestrators are responsible for:
- Coordinating multiple business operations
- Managing transactions across layers
- Launching asynchronous tasks
"""

from .llm_response_handler import process_llm_response

__all__ = ["process_llm_response"]
```

### 步骤2: 实现 llm_response_handler.py

**完整代码**：

```python
"""
LLM response processing orchestrator.

Coordinates the processing of LLM responses including:
- Relationship score updates
- Memory operations
- Request logging
- Message sending
"""

import asyncio
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.ai.relationship_scoring import determine_relationship_type
from services.ai.conversation_memory import process_memory_operations
from services.ai.queries.relationship_queries import get_instance_relationship_scores
from services.ai.queries.updates import (
    update_instance_relationship_scores,
    set_instance_current_relationship,
    update_instance_status,
    mark_conversation_item_as_excluded,
)
from services.ai.queries.transactions import save_ai_request_log
from services.message.processing.sender import send_ai_messages_with_typing
from services.message.processing.buffer import finalize_buffer_if_locked
from services.ai.types import InstanceContext
from utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TYPING_SPEED_WPM = 50
DEFAULT_TYPING_SPEED_SECONDS_PER_WORD = 60.0 / DEFAULT_TYPING_SPEED_WPM


async def process_llm_response(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    instance_context: InstanceContext,
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
    locked_buffer_id: Optional[int],
    user_message_item_id: Optional[int],
) -> Dict[str, Any]:
    """
    Persist LLM side effects (scores, memory, logs) and launch message sending task.

    This orchestrator coordinates:
    1. Relationship score updates
    2. Memory operations
    3. Attack detection handling
    4. Instance blocking
    5. Request logging
    6. Buffer finalization
    7. Asynchronous message sending

    Args:
        db: Database session
        session_factory: Session factory for async tasks
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id
        instance_context: Instance context dictionary
        ai_response: AI response from LLM
        llm_result: LLM result with metadata
        locked_buffer_id: Locked buffer ID
        user_message_item_id: User message item ID

    Returns:
        Dictionary with success status and buffer_id

    Raises:
        Exception: If processing fails (will rollback transaction)
    """
    try:
        new_scores = ai_response.get("score")
        memory_operations = ai_response.get("memory_operations")

        # Update relationship scores
        if new_scores:
            await update_instance_relationship_scores(db, instance_context["instance_id"], new_scores)

            latest_scores = await get_instance_relationship_scores(db, instance_context["instance_id"])
            if latest_scores:
                rel = await determine_relationship_type(db, instance_context, latest_scores)
                if rel and rel.get("relationship"):
                    relationship = rel["relationship"]
                    display_name = getattr(relationship, "display_name", getattr(relationship, "name", ""))
                    await set_instance_current_relationship(
                        db, instance_context["instance_id"], relationship.id, display_name
                    )

        # Process memory operations
        if memory_operations:
            await process_memory_operations(db, instance_qiao_id, memory_operations)

        # Handle attack detection
        if ai_response.get("attack_detected") and user_message_item_id:
            await mark_conversation_item_as_excluded(db, user_message_item_id)

        # Handle instance blocking
        if ai_response.get("should_block"):
            await update_instance_status(db, instance_qiao_id, status=3)

        # Save request log
        await save_ai_request_log(
            db=db,
            instance_context=instance_context,
            user_qiao_id=user_qiao_id,
            ai_response=ai_response,
            llm_result=llm_result,
            buffer_id=locked_buffer_id,
        )

        # Finalize buffer
        if locked_buffer_id:
            await finalize_buffer_if_locked(db, locked_buffer_id)

        await db.commit()

        logger.info(
            "conversation_result_saved",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
        )

    except Exception as e:
        await db.rollback()
        logger.error(
            "conversation_result_save_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            exc_info=True,
        )
        raise

    # Launch asynchronous message sending task
    outgoing_messages = ai_response.get("outgoing_messages", [])
    followup_messages = ai_response.get("followup_messages", [])

    should_reply = ai_response.get("should_reply", True)
    typing_speed_seconds_per_word = DEFAULT_TYPING_SPEED_SECONDS_PER_WORD
    followup_delay_seconds = 0.0

    if should_reply and (outgoing_messages or followup_messages):
        from services.ai.queries.instance_queries import get_instance_relationship_config
        from sqlalchemy import select
        from models.ai import AIInstance

        # Get typing speed
        stmt = select(AIInstance.typing_speed_wpm).where(AIInstance.qiao_id == instance_qiao_id)
        result = await db.execute(stmt)
        wpm = result.scalar_one_or_none()

        if wpm and wpm > 0:
            typing_speed_seconds_per_word = 60.0 / float(wpm)
        else:
            typing_speed_seconds_per_word = DEFAULT_TYPING_SPEED_SECONDS_PER_WORD

        # Get followup delay
        config = await get_instance_relationship_config(db, instance_qiao_id)
        if not config:
            raise ValueError("Missing followup_delay_ms configuration")

        followup_delay_ms = config.get("followup_delay_ms")
        if followup_delay_ms is None:
            raise ValueError("Missing followup_delay_ms configuration")
        followup_delay_seconds = followup_delay_ms / 1000.0
    else:
        outgoing_messages = []
        followup_messages = []

    asyncio.create_task(
        send_ai_messages_with_typing(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
            outgoing_messages=outgoing_messages,
            followup_messages=followup_messages,
            typing_speed_seconds_per_word=typing_speed_seconds_per_word,
            followup_delay_seconds=followup_delay_seconds,
        )
    )

    return {
        "success": True,
        "buffer_id": locked_buffer_id,
    }
```

### 步骤3: 修改 queries/transactions.py

**修改内容**：

1. **提取 `_save_ai_request_log` 为公开函数**：

```python
# 将函数签名从
async def _save_ai_request_log(...)

# 改为
async def save_ai_request_log(...)

# 移除所有 _ 前缀的调用
```

2. **删除 `process_llm_response` 函数**（整个函数删除，已移到 orchestrators）

3. **删除不再需要的 import**：

```python
# 删除这些 import
# from .relationship_queries import get_instance_relationship_scores
# from ..relationship_scoring import determine_relationship_type
# from ..conversation_memory import process_memory_operations
# from services.message.processing.buffer import finalize_buffer_if_locked
# from services.message.processing.sender import send_ai_messages_with_typing
```

4. **删除辅助函数**（如果只被 process_llm_response 使用）：

```python
# 删除这些函数
# async def _get_typing_speed_seconds_per_word(...)
# async def _get_followup_delay_ms(...)
```

**修改后的文件结构**：

```python
"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.

IMPORTANT: This is the data access layer - NO business logic imports allowed.
"""

import asyncio
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import func, select

from models.ai import AIInstance, AIConversationItemArchive, AIRequestLog
from models.profile import Profile
from models.contact import Contact
from .updates import (
    update_instance_relationship_scores,
    set_instance_current_relationship,
    update_instance_status,
    mark_conversation_item_as_excluded,
)
from .instance_queries import get_user_id_by_qiao_id, get_instance_relationship_config
from utils.logging import get_logger
from services.ai.types import InstanceContext

logger = get_logger(__name__)


async def create_instance_with_relations(db: AsyncSession, instance_data: Dict[str, Any]) -> str:
    """Create an instance with associated inventory in one transaction."""
    # ... 保持不变 ...


async def save_ai_request_log(
    db: AsyncSession,
    instance_context: InstanceContext,
    user_qiao_id: str,
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
    buffer_id: Optional[int],
) -> None:
    """Save AI request log with correct field mapping."""
    # ... 从 _save_ai_request_log 复制内容，移除 _ 前缀 ...


async def archive_contexts_transaction(
    db: AsyncSession, contexts_to_archive: list, instance_qiao_id: str
) -> int:
    """Archive contexts in a transaction."""
    # ... 保持不变 ...


async def archive_all_conversation_items(db: AsyncSession, user_qiao_id: str, instance_qiao_id: str) -> int:
    """Archive all conversation items for a user-instance pair."""
    # ... 保持不变 ...
```

### 步骤4: 更新 conversation_flow.py

**修改位置**: Line 378-379

```python
# 原代码
if persist:
    from core.database import SessionLocal
    from .queries.transactions import process_llm_response

    await process_llm_response(...)

# 修改为
if persist:
    from core.database import SessionLocal
    from .orchestrators.llm_response_handler import process_llm_response

    await process_llm_response(...)
```

### 步骤5: 更新 queries/__init__.py

**修改内容**：

```python
# 删除
from .transactions import (
    create_instance_with_relations,
)

# 改为
from .transactions import (
    create_instance_with_relations,
    save_ai_request_log,  # 新增：现在是公开函数
)

# 更新 __all__
__all__ = [
    # ... 其他导出 ...
    "create_instance_with_relations",
    "save_ai_request_log",  # 新增
]
```

### 步骤6: 验证修改

```bash
# 1. 检查语法错误
cd backend
python -m py_compile app/services/ai/orchestrators/llm_response_handler.py
python -m py_compile app/services/ai/queries/transactions.py
python -m py_compile app/services/ai/conversation_flow.py

# 2. 检查循环导入
python -c "import app.services.ai.conversation_flow"
python -c "import app.services.ai.queries.transactions"
python -c "import app.services.ai.orchestrators.llm_response_handler"

# 3. 运行类型检查（如果配置了 mypy）
mypy app/services/ai/

# 4. 运行测试
pytest tests/services/ai/ -v

# 5. 启动容器测试
cd ../deployment
docker-compose restart backend
docker-compose logs -f backend
```

## 验证标准

### 必须满足的条件

- [ ] 所有文件的 import 语句都在文件顶部（除了类型检查的 TYPE_CHECKING 块）
- [ ] `queries/` 目录下的文件不导入业务逻辑层（relationship_scoring, conversation_memory）
- [ ] 可以独立导入任何模块：`python -c "import app.services.ai.xxx"` 不报错
- [ ] 所有现有测试通过
- [ ] 类型检查通过（如果配置了）
- [ ] 容器启动正常，日志无错误
- [ ] 手动测试：发送消息到 AI 实例，验证完整流程正常

### 代码质量检查

- [ ] 没有未使用的 import
- [ ] 函数文档字符串完整
- [ ] 日志记录保持一致
- [ ] 错误处理保持一致

## 回滚方案

如果重构出现问题，执行以下步骤回滚：

```bash
# 1. 放弃所有修改
git checkout .
git clean -fd

# 2. 切回主分支
git checkout main

# 3. 删除功能分支
git branch -D refactor/remove-circular-imports
```

## 后续改进

### 1. 添加架构测试

安装 `import-linter`:

```bash
pip install import-linter
```

创建 `.importlinter`:

```ini
[importlinter]
root_package = app

[importlinter:contract:layers]
name = Enforce layered architecture in AI services
type = layers
layers =
    app.services.ai.orchestrators
    app.services.ai.relationship_scoring
    app.services.ai.conversation_memory
    app.services.ai.conversation_prompt
    app.services.ai.queries
```

### 2. 更新开发文档

在 `docs/development/architecture.md` 中添加：

```markdown
## AI Services 分层架构

### 层次说明

1. **Orchestration Layer** (`orchestrators/`)
   - 协调多个业务操作
   - 管理跨层事务
   - 启动异步任务
   - 可以导入：Business Logic Layer, Data Access Layer

2. **Business Logic Layer** (根目录)
   - 纯业务逻辑，无副作用
   - 可以导入：Data Access Layer, types.py
   - 禁止导入：Orchestration Layer

3. **Data Access Layer** (`queries/`)
   - 纯数据库操作
   - 只能导入：models, types.py
   - 禁止导入：Business Logic Layer, Orchestration Layer

### 依赖规则

- ✅ 上层 → 下层
- ❌ 下层 → 上层
- ✅ 同层之间（避免循环）
```

### 3. Code Review Checklist

在 PR 模板中添加：

```markdown
## 架构检查

- [ ] 没有在 `queries/` 中导入业务逻辑
- [ ] 没有新增局部 import（除非有充分理由）
- [ ] 遵守分层架构原则
```

## 常见问题

### Q: 为什么不直接合并模块？

A: 合并模块会导致：
- 单个文件过大，难以维护
- 职责不清晰
- 违反单一职责原则
- 改动范围更大，风险更高

### Q: orchestrators 和 business logic 的区别是什么？

A:
- **Business Logic**: 纯函数，无副作用，可独立测试（如计算分数、构建 prompt）
- **Orchestrators**: 协调多个操作，管理事务，有副作用（如保存数据、发送消息）

### Q: 如果未来还需要添加新的 orchestrator 怎么办？

A: 在 `orchestrators/` 目录下创建新文件，遵循相同的模式：
- 文件名：`{domain}_handler.py`
- 职责：协调特定领域的操作
- 导入：可以导入 business logic 和 queries

## 参考资料

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Layered Architecture Pattern](https://www.oreilly.com/library/view/software-architecture-patterns/9781491971437/ch01.html)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
