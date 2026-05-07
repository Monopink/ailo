# 记忆系统

本规范定义 AI 实例记忆的当前有效行为。

## 数据模型

- 模板记忆：`ai_template_memories`
- 实例记忆：`ai_instance_memories`

实例记忆字段约束：

- `memory_type`：`core` / `recent`
- `status`：`1`（active）/ `2`（archived）
- `normalized_content`：标准化内容，用于去重
- `source_strength`：来源强度（1-5）
- `fact_key`：规则命中的事实键（可空）
- `reinforce_count` / `last_reinforced_at`：强化信息

唯一约束：

- active 集合唯一：`(instance_id, normalized_content) WHERE status=1`

归档记录（`status=2`）允许多版本并存，用于审计追溯。

## 类型与治理目标

- `core`：长期稳定事实与长期偏好
- `recent`：短期上下文与阶段性信息

治理原则：

- `core` 只做读取限量，不做自动归档
- `recent` 在写入阶段执行遗忘治理与归档
- 读取阶段保持只读

## 配置

优先级：

1. `ai_instances.request_params`
2. `llm_configs.extra_params`
3. 默认值

有效配置项：

- `memory_limits.core`（默认 `30`）
- `memory_limits.recent`（默认 `50`）
- `memory_budget_tokens`（默认 `700`）

预算软超比例固定为 `15%`，硬上限为 `floor(memory_budget_tokens * 1.15)`。

## 统一写入策略

所有实例记忆写入入口统一经过 `memory_policy_service`：

- LLM `memory_operations`
- 模板记忆复制到实例
- Admin 实例记忆创建/更新

写入流程在单事务内执行，实例行先加锁（`FOR UPDATE`）。

固定执行链路：

1. 文本标准化
2. 去重候选判定
3. `fact_key` 判定
4. 冲突裁决
5. 写入/合并
6. `recent` 归档治理
7. 审计与指标

## 去重与冲突

### 文本去重

- 精确去重：`normalized_content` 相同即合并
- 近似去重：仅用于 `recent` 候选筛选，使用 `pg_trgm similarity >= 0.90`

近似去重只提供候选，不直接决定冲突覆盖。

### `fact_key` 冲突治理

`fact_key` 仅对固定槽位生成：

- `profile.residence_city`
- `profile.occupation`
- `relationship.partner_status`
- `preference.long_term`

无 `fact_key` 的记录不做自动冲突覆盖。

## 来源强度与权限

来源强度枚举：

- `5`：管理员显式写入
- `4`：结构化资料字段写入
- `3`：用户直接陈述（规则确认）
- `2`：模板复制或模型推断
- `1`：无来源标记

覆盖规则：

- 低来源强度不能覆盖高来源强度
- 同强度仅在 `fact_key` 相同且冲突可判定时覆盖
- LLM 来源（1-3）不能删除 `core`

## 读取与 Prompt

读取在 prompt 构建阶段执行，不修改数据库状态。

装载顺序：

1. 按 `core` 排序装载
2. 再按 `recent` 排序装载

排序规则：

- `core`：`source_strength desc -> importance desc -> reinforce_count desc -> updated_at desc -> id desc`
- `recent`：按 `utility_recent` 降序，再按 `importance/source_strength/reinforce_count/updated_at/id` 作为次序

预算控制：

- 先满足 `memory_limits` 数量保护
- 同时受 `memory_budget_tokens` 硬上限约束

## LLM 操作协议

`memory_operations` 操作顺序固定：`remove -> update -> refresh_ids -> add`。

- `remove`：按内容归档匹配记忆
- `update`：按旧内容定位后应用策略更新
- `refresh_ids`：仅作用于 `recent` active 记忆，受冷却时间限制
- `add`：新建或合并写入，由统一策略服务判定落入 `core` 或 `recent`

## 可观测性

关键指标：

- `memory_dedup_merge_count`
- `memory_conflict_detect_count`
- `memory_conflict_override_count`
- `memory_recent_archived_count`
- `memory_prompt_tokens`
- `memory_soft_budget_exceed_count`

关键审计事件：

- 冲突覆盖
- `core -> recent` 降级
- 归档触发（含入口）
