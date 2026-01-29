# 记忆系统

本规范记录 AI 记忆系统的长期约束，用于指导模型交互与后端实现。实施细节与任务跟踪请见 `docs/tasks/completed/ai-memory-system-design.md`。

## 数据模型

- 模板记忆：`docs/data-dict/ai-instantiation.md#ai_template_memories`
- 实例记忆：`docs/data-dict/ai-conversation.md#ai_instance_memories`

模板表用于静态种子数据，实例创建时按 `display_order` 拷贝到 `ai_instance_memories`，并补全 user/instance 字段。运行期的所有记忆都存放在实例表中，不再使用任何字符串类型的 `memory` 字段。 `ai_instance_memories` enforces a unique (instance_id, content) pair so repeated texts cannot appear within the same instance.
所有实例创建路径（`create_instance_from_persona` 与 `create_instance_with_relations`）都会调用 `copy_template_memories_to_instance` helper，保证以 `display_order` 顺序将模板记忆落库。

## 记忆类型与寿命

| 类型   | 用途                         | 过期规则 |
|--------|------------------------------|---------|
| core   | 用户长期事实、身份、关系等    | 永久保留，`expires_at = NULL` |
| recent | 临时状态、短期计划、上下文等  | `expires_at = (refreshed_at ?? created_at) + importance × 10 天` |

`importance ∈ [1, 10]`。AI 可通过 refresh 操作写入 `refreshed_at` 来重置 recent 记忆的寿命。

## 配置与数量限制

限制仅作用在检索阶段，写入淘汰暂不实现；如需写入时归档见 `docs/tasks/future-features-reserved.md`。回落顺序：

```
ai_instances.request_params.memory_limits
    ↓（缺失/非法）
llm_configs.extra_params.memory_limits
    ↓
DEFAULT_MEMORY_LIMITS（代码常量，core=30，recent=50）
```

模板/运行期超过上限只会在读取时被裁剪。

## 检索与 Prompt

检索在 system prompt 构建阶段执行，替换 `{{memory}}` 占位符：

1. 读取 core/recent 限制。
2. 查询 `ai_instance_memories`，过滤 `user_qiao_id`、`instance_qiao_id`、`status=1`；recent 额外要求 `expires_at > NOW()`。
3. 以 `importance desc, created_at desc` 排序，并在 core/recent 维度分别 `LIMIT`。
4. recent 记忆根据剩余寿命比例贴标签：
   - ≥75%：`[清晰]`
   - 50%-75%：`[较模糊]`
   - 25%-50%：`[很模糊]`
   - <25%：`[极模糊]`
5. 输出 Markdown，引导 AI 在“较模糊”及以上标签时使用“我记得”“好像”等措辞。

检索过程只读数据库，不会在此阶段修改 `status` 或其他字段；如需批量归档过期记录，后续单独交给后台任务。

## 记忆操作协议

LLM 响应中的 `memory_operations` 为对象，操作顺序固定：remove → update → refresh → add。匹配均基于 content 精确匹配。

- **remove**：字符串数组；命中后将记录 `status` 置为 2。
- **update**：对象数组（`old_content`、`new_content`、可选 `new_importance`）；原地修改，保留 `created_at`、`source_message_id`、`refreshed_at`。
- **refresh**：字符串数组；命中后仅更新 `refreshed_at`，触发器重算 `expires_at`。
- **add**：对象数组（`memory_type`、`content`、`importance`）；新建 `status=1` 记录，由触发器写入 `expires_at`。

若某项未匹配到记录，记录 WARNING 便于分析，但整体流程继续执行。

## Prompt 与 Schema 约束

- system prompt 必须说明两类记忆的用途、重要性范围，并限制 refresh 频率（每轮 1-2 条）。
- JSON Schema 强制包含 `should_update_memory`（bool）与 `memory_operations`（对象，可为空），并按上述结构定义四类操作。

## 参考代码

- `backend/app/services/ai/memory/config.py`
- `backend/app/services/ai/memory/retrieval.py`
- `backend/app/services/ai/memory/operations.py`
- `backend/app/services/ai/conversation_prompt.py`
