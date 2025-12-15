# AI记忆系统设计与实施

## 背景与范围
- 目标：以模板记忆为种子，所有运行期记忆统一落在 `ai_instance_memories`，由 AI 根据内容重要性自主管理。
- 范围：数据库结构、实例化流程、LLM prompt、memory_operations 处理链路以及 request_log 记录；监控/定时任务暂不纳入。
- 文档职责：本文件记录实施要点、临时决策、任务状态；稳定规范参见 `docs/spec/ai/memory-system.md`。

## 关键设计结论
1. **更新策略**：`memory_operations.update` 原地修改记录（内容/importance），保留创建与溯源信息；无“先删再增”步骤。
2. **数量限制**：仅在检索阶段执行 LIMIT，写入阶段允许超过上限，模板与运行期都不被阻止。
3. **过期与清理**：只依赖 `status/expires_at` 过滤；过期记录暂留在同一张表，不在检索流程里顺便改状态，后续若需要批处理再单独实现。
4. **监控与 request_log**：`request_log.response` 已包含完整记忆操作，当前不新增监控字段；需要分析时离线解析 JSON 即可。
5. **配置回落**：严格按照 `实例 → llm_configs.extra_params → DEFAULT_MEMORY_LIMITS` 的顺序，schema 以最新 spec 为准。
6. **Prompt 约束**：system prompt 需限制 refresh 频率（每轮 1-2 条）并提示模糊表达；LLM JSON Schema 强制 `memory_operations` 为对象并包含四类操作。
7. **索引策略**：`ai_instance_memories` 需具备 `(user_qiao_id, instance_qiao_id, status)`、`instance_id`、`expires_at`（partial）等索引，必要时考虑 `(instance_id, content)` 唯一约束用于 update/remove 匹配。

## 数据与 Schema 要点
- 模板表字段用于静态内容，新增/排序通过 `display_order` 控制；没有 `status`、`expires_at`。
- 实例表新增 `user_id`、`user_qiao_id`、`instance_qiao_id`、`source_message_id`、`status`、`refreshed_at`、`expires_at`。
- 触发器 `calculate_memory_expires_at` 负责 recent 记忆寿命计算：`(refreshed_at ?? created_at) + importance × 10 天`。
- SQL init（01_schema.sql）必须已经移除旧 `ai_instances.memory` / `ai_templates.memory` 字符串字段，并在初始化阶段创建两张记忆表及触发器，这也是“清理 SQL”的含义。

## 流程要点
### 模板 → 实例复制
- 统一通过 `backend/app/services/ai/memory/templates.py:copy_template_memories_to_instance` 完成拷贝逻辑，避免在实例化入口重复实现。
- `create_instance_from_persona` 已直接调用该 helper；`create_instance_with_relations` 也会在 `instance_data` 或 metadata 中存在 `template_id` 时执行同样的复制流程。
- 在实例创建时按 `display_order` 读取 `AI_TEMPLATE_MEMORIES`，逐条写入 `AI_INSTANCE_MEMORIES`。
- 复制时补全 `instance_id/user_id`、qiao_id 字段，`status=1`，`refreshed_at=None`，触发器自动写入 `expires_at`。

### 记忆检索
- 使用 `backend/app/services/ai/memory/config.py:get_memory_limits` 计算限制，并缓存默认值 `DEFAULT_MEMORY_LIMITS = {"core": 30, "recent": 50}`。
- 查询条件包含 `status=1`，recent 额外 `expires_at > NOW()`；排序 `importance desc, created_at desc`。
- recent 记忆按剩余寿命标记 `[清晰] / [较模糊] / [很模糊] / [极模糊]`，构建 Markdown 片段以替换 prompt 中的 `{{memory}}`。

### 记忆操作执行
- 入口：`backend/app/services/ai/memory/operations.py:process_memory_operations`，顺序为 remove → update → refresh → add。
- remove：按 content 精确匹配，多条命中全部置 `status=2`。
- update：匹配单条记录后就地修改 `content` 与可选 `importance`，不改 `created_at`。
- refresh：仅更新 `refreshed_at`，触发器重算 `expires_at`。
- add：写入新记录，`source_message_id`、`memory_type`、`importance` 由 LLM 返回。
- 任意操作找不到匹配只记 WARN 日志，流程继续；request_log 保存完整响应便于后续排查。

### Prompt 与响应处理
- `conversation_prompt.build_memory_prompt` 负责注入记忆文本；`conversation_flow` 需确保 context 中不再附带旧版 `memory` 字符串。
- LLM schema（`backend/app/services/ai/response_schema.py`）与 mock provider 必须输出新的 `memory_operations` 结构。
- `llm_response_handler` 应传入 `InstanceContext`、`source_message_id` 并调用新的 operations 服务。

## 监控与日志
- 现阶段仅依赖 request_log 保存的 LLM 响应；如需统计某类操作，可离线分析 JSON。
- 若后续要做实时监控，可通过 CDC 或后台任务聚合，但不在本轮范围内。

## 待办与风险
- [x] 数据访问层：补充 `AIInstanceMemory`/`AITemplateMemory` ORM、CRUD、pydantic schema 与 Starlette-Admin 视图，支撑模板/实例记忆的可视化管理。
- [x] 实例化流程：`create_instance_from_persona` 与 `create_instance_with_relations` 均通过 `copy_template_memories_to_instance` 在事务内复制模板记忆。
- [ ] Prompt 构建：确认所有 prompt builder（conversation、admin chat test、mock）均调用 `build_memory_prompt`。
- [ ] LLM 响应处理：收敛到 `process_memory_operations`，移除旧版 `conversation_memory.py`，同步更新 admin executor/facade。
- [ ] API Schema & Admin UI：去除 `memory` 字段，必要时展示 `memory_prompt` 或统计信息。
- [ ] JSON Schema & Mock：新版 schema 发布后同步更新文档与测试；mock provider 要给出 sample operations 以覆盖四类动作。
- [x] 索引/唯一约束：`ai_instance_memories` 使用 `(instance_id, content)` 唯一约束，避免重复记忆并配合精确匹配。
- [ ] 测试：补充实例复制、检索格式化、四类操作、错误日志的单元测试，以及 admin Chat Test 的集成验证（模板复制/operations lifecycle 用例已就绪，其余待补）。

## 注意事项
- 实现过程中如发现 schema 与代码不一致，优先更新 schema/文档，再改代码。
- 禁止引入“临时缓存”或“软删除 fallback”等 workaround；若操作难以落地要及时反馈。
- 发现设计空白（例如权限、API 输入）要先沟通确认后再写代码。
