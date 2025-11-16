# Character Context Refactor Task

## 背景
AI 角色聊天的测试页面 `ai_character/chat-test` 在运行时会抛出 `Character qiao_g6tBJSF7LtU0dQY9 not found for schema generation`。问题源于角色数据在同一条调用链上被重复查询并以不同结构返回，大量业务函数直接依赖 ORM 对象的字段，导致上下文缺失与类型无法约束。这背离了“查询一次、结构单一、依赖倒置”的架构原则。

## 问题诊断
- **重复查询**：validation、schema 构建、会话流程各自查询数据库，同一请求对同一角色至少执行 3 次查询。
- **结构不一致**：有的函数拿到扁平字典，有的收到 ORM 对象甚至混用，导致字段命名和可用性无法保证。
- **类型不安全**：当前上下文以 `Dict[str, Any]` 和 `Optional[...]` 填充，类型检查器无法识别缺字段问题，运行时才发现 `relationship_counts`、`request_params` 等关键字段缺失。
- **错误被吞掉**：查询函数把所有异常吞掉并返回 `None`，把数据库/序列化错误伪装成“角色不存在”，违反“不隐藏错误”的项目原则。
- **入口重复查询**：admin 校验流程先 `db.get(character_id)` 再根据 `qiao_id` 重新查上下文，仍然存在多次访问且无法保证事务视图一致。

## 目标
1. 单个请求中角色数据只查询一次，并在最外层构造统一上下文。
2. 所有业务层函数以严格的 `TypedDict(total=True)` 作为输入，彻底禁止 ORM 对象泄漏。
3. 错误路径只对“未找到”返回空，其余异常必须抛出并记录结构化日志。
4. 无过渡层，一次性替换旧结构，所有调用点立即切换到新上下文。

## 非目标
- 不中断或重写 LLM 服务逻辑与提示词内容。
- 不在本次迭代内优化数据库索引或分库策略。

## 架构方案
### 1. `CharacterContext` 类型模型
- 在 `backend/app/services/ai/types.py` 新增以下结构：
  - `RelationshipCounts`, `DimensionSpec`, `CurrentRelationship`, `StyleInfo`, `PersonalityInfo`, `ProfileInfo` 等子 `TypedDict`。
  - 顶层 `CharacterContext(total=True)` 聚合所有字段，并将 `prompt_variables`、`request_params` 设为 `Dict[str, Any]`（初始化为空字典）以避免 `Optional`。
- 确保类型定义覆盖 `relationship_counts`、`request_params`、`prompt_variables`、`created_from_profile_qiao_id`、`current_relationship` 等所有已知依赖字段。

### 2. 数据访问层
- 在 `services/ai/queries/character_queries.py` 新增 `get_character_context`：
  - 接收 `character_id` 或 `character_qiao_id`（至少一个）。
  - 单次查询 JOIN `AICharacter`, `AIStyle`, `AIPersonality`, `Profile`, `AIRelationship`，并使用第二条查询获取维度列表。
  - 仅在无记录时返回 `None`；否则抛出 `AIDataAccessError` 并记录事件，避免静默失败。
  - 删除旧的 `get_character_with_relations`，不残留兼容函数。

### 3. 业务层纯函数
- `conversation_prompt.py`：`build_response_schema`、`build_system_prompt`、`_build_placeholder_values` 全部改为 `(context: CharacterContext, ...)`，只依赖上下文和传入参数，禁止内部查询角色信息。
- `relationship_scoring.py`：`determine_relationship_type`、`calculate_new_scores` 读取 `context["relationship_counts"]`、`context["current_relationship"]` 等字段。
- 其他使用角色信息的模块一律改为从 `context` 取数据，保证函数保持纯输入输出。

### 4. 应用层入口
- `process_conversation`、`validate_character_test_prerequisites`、`testing/character_chat` 等入口函数在第一步获取 `CharacterContext` 并贯穿整个流程。
- admin 校验直接复用上下文进行所有检查（维度、人格状态、schema 构建等）。
- 调用链中禁止再次查询角色信息，确保上下文是单一真相源。

## 实施步骤
1. **类型定义**：新增 `types.py` 并引入所有子 `TypedDict`，调整 `__all__` 暴露。
2. **查询函数**：实现 `get_character_context` 并删除旧查询；更新依赖模块导入。
3. **上下文消费**：逐个模块替换参数与实现，确保不残留 ORM 访问；同步更新测试或调用示例。
4. **入口改造**：更新所有入口层逻辑，只保留一次上下文查询；admin 校验去掉 `db.get` 重复查询。
5. **错误处理**：引入/复用 `AIDataAccessError`（或新异常类型），确保日志包含 `character_id`/`character_qiao_id`。
6. **验证**：运行类型检查 + 针对 `ai_character/chat-test` 的端到端测试，确认 schema 构建和会话流程只执行一次角色查询。

## 测试与验收
- 执行 mypy/pyright（或项目已有类型检查）确保所有 `context[...]` 访问符合类型定义。
- 手动/自动测试 `ai_character/chat-test`，确认 response schema 成功生成，错误情况能准确抛出。
- 检查日志，确保数据库异常不再被当作“角色不存在”吞掉。
