# AI 角色上下文架构重构方案（2.0）

## 问题诊断

### 当前问题

测试页面报错：`Character qiao_g6tBJSF7LtU0dQY9 not found for schema generation`

### 根本原因

**架构设计缺陷**：缺乏明确的数据流边界和职责分层

1. **数据层、领域层、应用层职责不清**：每个模块各自查询数据库
2. **ORM 对象泄漏到业务层**：导致强耦合，违反依赖倒置原则
3. **没有统一的"角色上下文"概念**：同一数据被查询 3 次，结构还不一致

### 详细问题分析

#### 1. 数据查询重复（3次）

```
┌─────────────────────────────────────────────────────────────┐
│ validation_service.validate_character_test_prerequisites    │
│ ├─ _validate_character (查询 AICharacter)                   │
│ ├─ _validate_character_profile (查询 Profile)               │
│ ├─ _validate_ai_configuration (查询 AIStyle, AIPersonality) │
│ └─ _validate_relationship_scores (查询 dimensions)          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ validate_test_readiness                                      │
│ └─ get_response_schema(db, character_qiao_id)               │
│    └─ get_character_with_relations() ← 重复查询！           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ process_conversation                                         │
│ └─ get_character_with_relations() ← 再次重复查询！          │
└─────────────────────────────────────────────────────────────┘
```

**问题**：

- 同一个角色数据在一次请求中被查询 3 次
- 不同查询函数返回的数据结构不一致
- 可能因为数据库会话、事务隔离导致查询结果不一致

#### 2. 数据结构不统一

**validation_service 返回**：

```python
{
    "character": {"id": int, "qiao_id": str, ...},  # 扁平字典
    "style": {"id": int, "name": str, ...},
    "personality": {...}
}
```

**get_character_with_relations 返回**：

```python
{
    "character": <AICharacter ORM 对象>,  # ORM 对象！
    "style": <AIStyle ORM 对象>,
    "personality": <AIPersonality ORM 对象>
}
```

**问题**：不同模块对同一数据有不同的理解和使用方式

#### 3. ORM 对象依赖广泛

代码中大量依赖 ORM 对象的属性访问：

| 文件 | 代码 | 问题 |
|------|------|------|
| conversation_prompt.py | `character.prompt_variables` | ORM 依赖 |
| conversation_prompt.py | `character.memory` | ORM 依赖 |
| conversation_flow.py | `character.request_params` | ORM 依赖 |
| relationship_scoring.py | `character.relationship_counts` | **关键字段** |

**关键发现**：`relationship_counts` 字段对关系限流至关重要，但在原方案中被遗漏了。

#### 4. 职责混乱

- `get_response_schema` 既查询数据又构建 schema（违反 SRP）
- `build_system_prompt` 既接受 character_info 又查询数据库（职责不清）
- 高层模块依赖低层查询（违反 DIP）

---

## 最佳架构方案

### 核心设计原则

1. **CharacterContext 是完全扁平化的 TypedDict**
   - ✅ 包含所有字段（不遗漏任何关键数据，包括 `relationship_counts`、`request_params` 等）
   - ✅ 只包含基本类型（int, str, dict, list）
   - ✅ **不包含任何 ORM 对象**（这是关键）

2. **单一数据源（Single Source of Truth）**
   - 在请求入口处查询一次 `get_character_context()`
   - 所有后续操作传递同一份 CharacterContext

3. **依赖倒置（Dependency Inversion）**
   - 业务层函数签名：`func(context: CharacterContext, ...) -> Result`
   - 业务层不访问数据库，只处理纯数据

4. **职责分离（Separation of Concerns）**
   - **数据层**：查询数据库，构建 CharacterContext
   - **业务层**：纯函数，接受 CharacterContext，执行逻辑
   - **应用层**：编排流程，传递 CharacterContext

5. **符合 SOLID 原则**：每个函数只做一件事，接口清晰

### 方案概览

```
┌─────────────────────────────────────────────────────────────┐
│ 入口层 (Controller/Service Facade)                          │
│ ├─ process_conversation()                                   │
│ ├─ validate_test_readiness()                                │
│ └─ 职责：查询 CharacterContext 一次，传递给业务层           │
└─────────────────────────────────────────────────────────────┘
                          ↓ CharacterContext
┌─────────────────────────────────────────────────────────────┐
│ 数据层 (Data Layer)                                          │
│ └─ get_character_context(db, qiao_id) -> CharacterContext   │
│    - 单一查询，包含所有 JOIN                                 │
│    - 返回纯数据结构（无 ORM 对象）                           │
└─────────────────────────────────────────────────────────────┘
                          ↓ CharacterContext
┌─────────────────────────────────────────────────────────────┐
│ 业务层 (Business Layer) - 纯函数                             │
│ ├─ build_response_schema(context) -> Dict                   │
│ ├─ build_system_prompt(context, ...) -> str                 │
│ ├─ determine_relationship_type(context, scores) -> Dict     │
│ └─ 特点：无数据库访问，可测试，可复用                        │
└─────────────────────────────────────────────────────────────┘
```

**关键改进**：

- ✅ 所有业务函数接受 `CharacterContext` 而不是 `character_qiao_id`
- ✅ 数据只查询一次，在最外层（controller/service facade）
- ✅ 业务函数是纯函数，不依赖数据库查询
- ✅ **不包含任何 ORM 对象**，真正实现依赖倒置
- ✅ validation_service 直接返回 CharacterContext，测试和正式流程共用

---

## 实施步骤

### 第一步：定义完整的 CharacterContext

**文件**：`backend/app/services/ai/types.py`（新建）

```python
"""
AI service type definitions.

Defines standard data structures used across AI services to ensure consistency
and avoid redundant database queries.
"""

from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict


class CharacterContext(TypedDict, total=False):
    """
    Standard character context - single source of truth for character data.

    Design principles:
    - Pure data structure (NO ORM objects)
    - Complete (all fields needed by business logic)
    - Flat (no nested ORM objects)
    - Used by all AI service functions as input parameter

    Migration notes:
    - Replaces get_character_with_relations() return value
    - All business functions should accept this instead of character_qiao_id
    - Queried once at request entry point, passed through all layers
    """

    # ========== Character Fields ==========
    character_id: int
    character_qiao_id: str
    category: Optional[str]
    memory: Optional[str]
    prompt_variables: Optional[Dict[str, Any]]  # Prompt variable overrides
    request_params: Optional[Dict[str, Any]]    # LLM request parameters
    typing_speed_wpm: int
    user_id: Optional[int]
    user_qiao_id: Optional[str]
    relationship_id: Optional[int]
    relationship_counts: Optional[Dict[str, Any]]  # ← KEY: Relationship rate limiting
    status: int
    created_from_profile_qiao_id: Optional[str]
    created_by: int

    # ========== Style Fields ==========
    style_id: int
    style_name: str
    style_display_name: str

    # ========== Personality Fields ==========
    personality_id: int
    personality_name: str
    personality_display_name: str
    personality_prompt: str
    personality_status: int

    # ========== Profile Fields ==========
    profile_nickname: str
    profile_bio: Optional[str]
    profile_gender: Optional[int]
    profile_avatar_url: Optional[str]
    profile_avatar_prompt: Optional[str]
    profile_region: Optional[str]

    # ========== Dimensions (for schema generation) ==========
    dimensions: List[Dict[str, Any]]
    # Format: [{"id": int, "name": str, "display_name": str, "initial_position": int}, ...]

    # ========== Current Relationship (optional) ==========
    current_relationship: Optional[Dict[str, Any]]
    # Format: {"id": int, "name": str, "display_name": str, "prompt_fragment": str}


__all__ = ["CharacterContext"]
```

**关键设计决策**：

✅ **完全扁平化**：只包含基本类型（int, str, dict, list），不包含任何 ORM 对象
✅ **完整性**：包含所有业务需要的字段，特别是：

- `relationship_counts`：关系限流的关键字段
- `request_params`：LLM 请求参数
- `prompt_variables`：提示词变量覆盖
- `created_from_profile_qiao_id`：创建来源追踪

✅ **类型安全**：使用 TypedDict 提供类型检查
✅ **单一职责**：作为所有 AI 服务函数的标准输入

---

### 第二步：创建统一查询函数

**文件**：`backend/app/services/ai/queries/character_queries.py`

**修改内容**：

1. **新增函数** `get_character_context()`（替代 `get_character_with_relations()`）
2. **删除函数** `get_character_with_relations()`（不保留向后兼容）

```python
async def get_character_context(
    db: AsyncSession,
    character_qiao_id: str
) -> Optional[CharacterContext]:
    """
    Get complete character context in standardized format.

    This is the SINGLE source of truth for character data queries.
    All services should use this function instead of querying separately.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        CharacterContext with all required data, or None if not found

    Design notes:
    - Single comprehensive query with all necessary joins
    - Returns pure data structure (NO ORM objects)
    - Includes ALL fields needed by business logic
    - Replaces get_character_with_relations()
    """
    try:
        # Single comprehensive query with all joins
        result = await db.execute(
            select(AICharacter, AIPersonality, AIStyle, Profile, AIRelationship)
            .join(AIPersonality, AICharacter.personality_id == AIPersonality.id)
            .join(AIStyle, AICharacter.style_id == AIStyle.id)
            .join(
                Profile,
                and_(Profile.owner_qiao_id == AICharacter.qiao_id, Profile.owner_type == 2),
            )
            .outerjoin(AIRelationship, AICharacter.relationship_id == AIRelationship.id)
            .where(AICharacter.qiao_id == character_qiao_id)
        )

        row = result.first()
        if not row:
            logger.warning("character_not_found", character_qiao_id=character_qiao_id)
            return None

        character, personality, style, profile, relationship = row

        # Get dimensions for the style (separate query, but only once)
        dimensions_result = await db.execute(
            select(
                AIDimension.id.label("id"),
                AIDimension.name.label("name"),
                AIDimension.display_name.label("display_name"),
                AIStyleDimension.initial_position.label("initial_position"),
            )
            .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
            .where(AIStyleDimension.style_id == style.id)
            .order_by(AIDimension.name)
        )
        dimensions = [
            {
                "id": row.id,
                "name": row.name,
                "display_name": row.display_name,
                "initial_position": row.initial_position,
            }
            for row in dimensions_result
        ]

        # Build standardized context (pure data, NO ORM objects)
        from ..types import CharacterContext

        context: CharacterContext = {
            # ========== Character Fields ==========
            "character_id": character.id,
            "character_qiao_id": character.qiao_id,
            "category": character.category,
            "memory": character.memory,
            "prompt_variables": character.prompt_variables,
            "request_params": character.request_params,
            "typing_speed_wpm": character.typing_speed_wpm,
            "user_id": character.user_id,
            "user_qiao_id": character.user_qiao_id,
            "relationship_id": character.relationship_id,
            "relationship_counts": character.relationship_counts,  # ← KEY field
            "status": character.status,
            "created_from_profile_qiao_id": character.created_from_profile_qiao_id,
            "created_by": character.created_by,

            # ========== Style Fields ==========
            "style_id": style.id,
            "style_name": style.name,
            "style_display_name": style.display_name,

            # ========== Personality Fields ==========
            "personality_id": personality.id,
            "personality_name": personality.name,
            "personality_display_name": personality.display_name,
            "personality_prompt": personality.prompt,
            "personality_status": personality.status,

            # ========== Profile Fields ==========
            "profile_nickname": profile.nickname,
            "profile_bio": profile.bio,
            "profile_gender": profile.gender,
            "profile_avatar_url": profile.avatar_url,
            "profile_avatar_prompt": profile.avatar_prompt,
            "profile_region": profile.region,

            # ========== Dimensions ==========
            "dimensions": dimensions,

            # ========== Current Relationship (may be None) ==========
            "current_relationship": {
                "id": relationship.id,
                "name": relationship.name,
                "display_name": relationship.display_name,
                "prompt_fragment": relationship.prompt_fragment,
            } if relationship else None,
        }

        logger.debug(
            "character_context_retrieved",
            character_qiao_id=character_qiao_id,
            dimensions_count=len(dimensions),
            has_relationship=relationship is not None,
        )

        return context

    except Exception as e:
        logger.error(
            "character_context_query_failed",
            error=str(e),
            character_qiao_id=character_qiao_id,
        )
        return None
```

**关键点**：

- ✅ 包含所有字段，特别是 `relationship_counts` 和 `created_from_profile_qiao_id`
- ✅ 返回纯数据结构，不包含任何 ORM 对象
- ✅ 单一查询，包含所有必要的 JOIN
- ✅ 删除 `get_character_with_relations()`，不保留向后兼容

---

### 第三步：重构业务层函数

所有业务层函数改为接受 `CharacterContext` 作为参数，成为纯函数。

#### 3.1 重构 schema 构建函数

**文件**：`backend/app/services/ai/conversation_prompt.py`

```python
def build_response_schema(context: CharacterContext) -> Dict[str, Any]:
    """
    Build JSON schema from character context (pure function).

    Args:
        context: Character context with all required data

    Returns:
        JSON schema dictionary

    Raises:
        AIServiceError: If context data is invalid
    """
    try:
        dimensions = context.get("dimensions", [])

        # Validate dimensions - no default values allowed
        if not dimensions or len(dimensions) == 0:
            raise AIServiceError(
                ai_service="schema_building",
                reason="empty_dimensions",
                message=f"Style {context['style_id']} has no active dimensions.",
            )

        # Build score properties dynamically from dimensions
        score_properties = {}
        score_required = []

        for dimension in dimensions:
            dimension_name = dimension.get("name")
            if not dimension_name or not isinstance(dimension_name, str):
                raise AIServiceError(
                    ai_service="schema_building",
                    reason="invalid_dimension_name",
                    message=f"Invalid dimension name: {dimension_name}",
                )
            score_properties[dimension_name] = {"type": "integer", "minimum": 0, "maximum": 1000}
            score_required.append(dimension_name)

        return _get_base_response_schema(score_properties, score_required)

    except AIServiceError:
        raise
    except Exception as e:
        logger.error("dynamic_schema_build_failed", error=str(e))
        raise AIServiceError(
            ai_service="schema_building",
            reason="build_failed",
            message=f"Failed to build schema: {str(e)}",
        )
```

**关键点**：

- ✅ 纯函数，不访问数据库
- ✅ 所有数据来自 `context` 参数
- ✅ 易于测试，无需 mock

#### 3.2 重构 system prompt 构建函数

**文件**：`backend/app/services/ai/conversation_prompt.py`

```python
async def build_system_prompt(
    db: AsyncSession,
    context: CharacterContext,
    relationship_type: Optional[Dict[str, Any]],
    user_qiao_id: str,
) -> str:
    """
    Build complete system prompt for AI character.

    Args:
        db: Database session (only for dynamic data like user profile)
        context: Character context with all static data
        relationship_type: Relationship type information
        user_qiao_id: User's qiao_id

    Returns:
        Complete system prompt string
    """
    personality_prompt = context["personality_prompt"]

    # Build placeholder values
    placeholder_values = await _build_placeholder_values(
        db, context, relationship_type, user_qiao_id
    )

    # Apply character-specific prompt variables (overrides)
    character_prompt_variables = context.get("prompt_variables") or {}
    placeholder_values.update(character_prompt_variables)

    # Replace placeholders
    system_prompt = replace_placeholders(personality_prompt, placeholder_values)

    return system_prompt
```

**关键点**：

- ✅ 接受 `CharacterContext` 而不是 `character_info` 字典
- ✅ 只查询动态数据（用户 profile、pending messages）
- ✅ 所有角色数据来自 `context` 参数

#### 3.3 重构 relationship scoring 函数

**文件**：`backend/app/services/ai/relationship_scoring.py`

```python
async def determine_relationship_type(
    db: AsyncSession,
    context: CharacterContext,
    relationship_scores: Dict[str, int],
) -> Dict[str, Any]:
    """
    Determine relationship type based on scores.

    Args:
        db: Database session
        context: Character context
        relationship_scores: Current relationship scores

    Returns:
        Relationship type information
    """
    # Use context fields instead of ORM object
    relationship_id = context.get("relationship_id")
    relationship_counts = context.get("relationship_counts") or {}

    # ... rest of logic using context fields
```

**关键点**：

- ✅ 使用 `context["relationship_counts"]` 而不是 `character.relationship_counts`
- ✅ 所有字段从 `context` 获取，不依赖 ORM 对象

---

### 第四步：重构入口层

#### 4.1 重构 process_conversation

**文件**：`backend/app/services/ai/conversation_flow.py`

```python
async def process_conversation(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    message_content: str,
    # ... other parameters
) -> Dict[str, Any]:
    """
    Process AI conversation.

    REFACTORED: Queries character context once at the beginning.
    """
    # Step 1: Get character context (SINGLE QUERY)
    from .queries import get_character_context

    context = await get_character_context(db, character_qiao_id)
    if not context:
        raise AIConversationError(
            conversation_step="character_lookup",
            reason="character_not_found",
            message=f"Character not found: {character_qiao_id}",
        )

    # Step 2: Validate message permission (using context)
    character_status = context["status"]
    # ... validation logic

    # Step 3: Get relationship scores
    relationship_scores = await get_relationship_scores(db, character_qiao_id)

    # Step 4: Determine relationship type (using context)
    relationship_type = await determine_relationship_type(db, context, relationship_scores)

    # Step 5: Build system prompt (using context)
    system_prompt = await build_system_prompt(db, context, relationship_type, user_qiao_id)

    # Step 6: Build conversation history
    conversation_history = await build_conversation_context(
        db, character_qiao_id, user_qiao_id, max_context_length=None
    )

    # Step 7: Build response schema (using context, NO DATABASE QUERY)
    json_schema = build_response_schema(context)

    # Step 8: Extract request parameters (using context)
    character_request_params = context.get("request_params") or {}

    # ... rest of LLM invocation logic
```

**关键点**：

- ✅ 在入口处查询一次 `get_character_context()`
- ✅ 所有后续操作使用 `context`，不再查询数据库
- ✅ `build_response_schema(context)` 是纯函数调用，无数据库访问

#### 4.2 重构 validation_service

**文件**：`backend/app/services/admin/testing/validation.py`

```python
async def validate_character_test_prerequisites(
    db: AsyncSession,
    character_id: int
) -> CharacterContext:
    """
    Validate character test prerequisites.

    REFACTORED: Returns CharacterContext directly instead of分散的字典.

    Returns:
        CharacterContext with all required data

    Raises:
        ValidationError: If validation fails
    """
    # Get character qiao_id
    character = await db.get(AICharacter, character_id)
    if not character:
        raise ValidationError(error="character_not_found")

    # Get complete context (SINGLE QUERY)
    from services.ai.queries import get_character_context

    context = await get_character_context(db, character.qiao_id)
    if not context:
        raise ValidationError(error="character_context_not_found")

    # Validate dimensions
    if not context.get("dimensions"):
        raise ValidationError(error="no_dimensions")

    # Validate personality
    if context["personality_status"] != 1:
        raise ValidationError(error="personality_inactive")

    # Return complete context (not分散的字典)
    return context
```

**关键点**：

- ✅ 直接返回 `CharacterContext`，不是分散的字典
- ✅ 测试和正式流程共用同一份上下文

#### 4.3 重构测试服务

**文件**：`backend/app/services/admin/testing/character_chat/__init__.py`

```python
async def validate_test_readiness(
    self,
    db: AsyncSession,
    character_id: int
) -> Dict[str, Any]:
    """
    Check test readiness.

    REFACTORED: Uses context from validation, no re-querying.
    """
    # Validate prerequisites (returns CharacterContext)
    context = await validation_service.validate_character_test_prerequisites(
        db=db, character_id=character_id
    )

    # Check test user availability
    user_match_result = await user_matcher_service.find_test_user_for_character(
        db=db, character_qiao_id=context["character_qiao_id"]
    )

    # Build response schema (NO DATABASE QUERY)
    from services.ai.conversation_prompt import build_response_schema
    response_schema = build_response_schema(context)

    return {
        "ready": True,
        "context": context,
        "response_schema": response_schema,
        "test_user": user_match_result,
    }
```

**关键点**：

- ✅ 使用 validation 返回的 `CharacterContext`
- ✅ 不再重复查询数据库
- ✅ `build_response_schema(context)` 是纯函数调用

---

## 需要修改的模块清单

**一次性彻底重构，不保留过渡方案：**

1. ✅ **新建** `backend/app/services/ai/types.py` - 定义 `CharacterContext`
2. ✅ **修改** `queries/character_queries.py`
   - 新增 `get_character_context()`
   - **删除** `get_character_with_relations()`
3. ✅ **修改** `conversation_prompt.py`
   - `build_response_schema(context)` - 纯函数
   - `build_system_prompt(db, context, ...)` - 接受 context
   - `_build_placeholder_values(db, context, ...)` - 接受 context
4. ✅ **修改** `conversation_flow.py`
   - `process_conversation()` - 入口查询一次
5. ✅ **修改** `relationship_scoring.py`
   - `determine_relationship_type(db, context, scores)` - 接受 context
   - `calculate_new_scores(db, context, ...)` - 接受 context
6. ✅ **修改** `validation_service.py`
   - 返回 `CharacterContext` 而非分散字典
7. ✅ **修改** `testing/character_chat/`
   - 使用 validation 返回的 `CharacterContext`

---

## 总结

### 核心设计决策

1. ✅ **CharacterContext 是完全扁平化的 TypedDict**
   - 包含所有字段（包括 `relationship_counts`、`request_params` 等）
   - 只包含基本类型（int, str, dict, list）
   - **不包含任何 ORM 对象**

2. ✅ **单一数据源**
   - 在请求入口处查询一次 `get_character_context()`
   - 所有后续操作传递同一份 CharacterContext

3. ✅ **依赖倒置**
   - 业务层函数：`func(context: CharacterContext, ...) -> Result`
   - 业务层不访问数据库，只处理纯数据

4. ✅ **职责分离**
   - 数据层：查询数据库，构建 CharacterContext
   - 业务层：纯函数，接受 CharacterContext
   - 应用层：编排流程，传递 CharacterContext

5. ✅ **彻底重构**
   - 删除 `get_character_with_relations()`
   - validation_service 直接返回 CharacterContext
   - 测试和正式流程共用同一份上下文

### 优势

- ✅ **消除重复查询**：从 3 次减少到 1 次
- ✅ **数据结构统一**：所有模块使用相同的 CharacterContext
- ✅ **真正解耦**：业务层不依赖 ORM 对象
- ✅ **易于测试**：纯函数，无需 mock 数据库
- ✅ **符合 SOLID 原则**：依赖倒置、单一职责、职责分离

### 与原方案对比

| 方案 | ORM 对象 | 字段完整性 | 向后兼容 | 评价 |
|------|---------|-----------|---------|------|
| 原方案 | ❌ 无 | ❌ 缺少关键字段 | - | 不可用 |
| temp.md | ✅ 保留 | ✅ 完整 | ✅ 是 | 妥协设计 |
| **最终方案** | ❌ 无 | ✅ 完整 | ❌ 否 | **最佳** |

**最终方案**符合你的要求：

- ✅ 不考虑最小修改
- ✅ 不使用过渡方案
- ✅ 从第一性原理出发
- ✅ 找出问题根源
- ✅ 使用正确的架构
