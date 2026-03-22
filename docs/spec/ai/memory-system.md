# 记忆系统

本规范记录 AI 记忆系统的长期约束，用于指导模型交互与后端实现。

## 数据模型

- 模板记忆：`../../data-dict/ai-instantiation.md#ai_template_memories`
- 实例记忆：`../../data-dict/ai-conversation.md#ai_instance_memories`

模板表用于静态种子数据，实例创建时按 `display_order` 拷贝到 `ai_instance_memories`，并补全 user/instance 字段。运行期的所有记忆都存放在实例表中。 `ai_instance_memories` 强制使用唯一的（instance_id，content）对，这样重复的文本就不会出现在同一个 instance 中。
实例创建入口通过 `copy_template_memories_to_instance` helper 以 `display_order` 顺序落库模板记忆。模板记忆复制异常时，实例创建事务回滚。

## 记忆类型与寿命

| 类型   | 用途                         | 过期规则 |
|--------|------------------------------|---------|
| core   | 用户长期事实、身份、关系等    | 永久保留，`expires_at = NULL` |
| recent | 临时状态、短期计划、上下文等  | `expires_at = (refreshed_at ?? created_at) + importance × 10 天` |

`importance ∈ [1, 10]`。AI 可通过 refresh 操作写入 `refreshed_at` 来重置 recent 记忆的寿命。

## 配置与数量限制

数量限制仅在检索阶段生效；写入阶段按原样写入。

```
ai_instances.request_params.memory_limits
    ↓（缺失/非法：记录 WARNING 并使用下一来源）
llm_configs.extra_params.memory_limits
    ↓
硬上限（固定值）：core=30，recent=50
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

检索过程只读数据库，不会在此阶段修改 `status` 或其他字段。

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
