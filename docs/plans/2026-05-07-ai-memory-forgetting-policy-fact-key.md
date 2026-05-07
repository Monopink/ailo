# AI 记忆遗忘治理（有限 fact_key + 统一策略网关）

## 问题点

1. `memory_limits` 当前仅在读取阶段裁剪，写入阶段缺少统一归档治理，`recent` 容易堆积低价值记录。
2. 记忆写入入口分散（LLM 副作用、模板复制、Admin 写入），策略口径不一致。
3. 在单次 LLM 请求架构下，`core` 缺少来源权限约束，存在低可信写入污染高价值记忆的风险。
4. 现有唯一约束 `(instance_id, content)` 无法同时满足“active 去重”和“归档多版本审计可追溯”。
5. 纯文本近似去重与事实冲突裁决职责未分离，容易把“文本相似”误当“事实等价”。

## 需求点

1. 保持单次请求直接回复，不引入 agents 检索、向量检索、额外 LLM 摘要请求。
2. 建立统一记忆策略网关，所有实例记忆写入入口强制通过同一链路。
3. 读取链路保持只读，不在 prompt 构建阶段执行归档写入。
4. `core` 仅允许高可信来源写入/覆盖，LLM 低可信来源禁止直接覆盖高可信 `core`。
5. `recent` 执行遗忘衰减与预算治理，归档后永久保留，不执行硬删除。
6. 引入有限槽位 `fact_key`，仅用于高价值可判定事实冲突治理。

## 本次实施边界

1. 本次实施统一归档策略与统一写入网关。
2. 本次不拆分独立“归档服务（独立进程/调度器）”，归档逻辑内聚在 `memory_policy_service`。
3. 本次不引入后台异步记忆加工任务。

## 统一归档实施形态

1. 本次“统一归档”指统一归档策略入口，不指独立进程服务。
2. `memory_policy_service` 内部提供统一归档方法：`archive_recent_over_limit(...)`。
3. 所有实例记忆写入口在同一事务内调用该方法，禁止各入口自行实现归档。
4. 归档方法输入固定为：实例标识、active recent 集合、预算参数、排序规则。
5. 归档方法输出固定为：保留列表、归档列表、归档原因、审计事件载荷。
6. 本次不包含定时任务、消息队列消费者、独立部署单元。

## 冻结参数

- 用户重复确认阈值：`2` 轮。
- 近似去重阈值：`similarity >= 0.90`（`pg_trgm`）。
- 近似去重最小文本长度：`>= 8` 字符。
- `recent` 半衰期：`3` 天。
- `refresh` 冷却时间：`12` 小时。
- 同条 `refresh` 收益递减系数：`0.7`。
- 预算软超比例：`15%`。

## 实施方案

### 1) 统一策略网关

- 新增 `memory_policy_service` 作为唯一实例记忆写入口。
- 以下入口全部改造为调用统一网关：
  - LLM `memory_operations`（`remove/update/refresh_ids/add`）
  - 模板记忆复制到实例
  - Admin 实例记忆创建/更新
- 入口层禁止直接写 `ai_instance_memories`。

### 2) 事务与并发控制

- 每次实例记忆写入在单事务内完成。
- 事务开始后对目标 `ai_instances.id` 执行 `FOR UPDATE`。
- 同一事务内按固定顺序执行：标准化 -> 去重候选 -> `fact_key` 判定 -> 冲突裁决 -> 写入/归档 -> 审计记录。

### 3) 数据模型与唯一约束

- `ai_instance_memories` 新增字段：
  - `normalized_content`
  - `reinforce_count`（默认 `0`）
  - `last_reinforced_at`
  - `source_strength`（1-5）
  - `fact_key`（可空）
  - `conflict_flag`（可空）
- 唯一约束调整为 active 集合唯一：
  - `UNIQUE(instance_id, normalized_content) WHERE status=1`
- 归档记录允许多版本并存（`status=2`），用于审计追溯。

### 4) 有限 fact_key 生成

- 仅对固定高价值槽位生成 `fact_key`：
  - `profile.residence_city`
  - `profile.occupation`
  - `relationship.partner_status`
  - `preference.long_term`
- 仅当规则命中置信度达到阈值时写入 `fact_key`；未达阈值不生成。
- 无 `fact_key` 的记录不参与自动冲突覆盖，只允许并存或去重合并。

### 5) 来源强度与覆盖权限矩阵

- 来源强度：
  - `5`：管理员显式写入
  - `4`：结构化资料字段写入
  - `3`：用户直接陈述（命中确认规则）
  - `2`：模板复制或模型推断
  - `1`：无来源标记
- 覆盖规则：
  - 低来源强度禁止覆盖高来源强度。
  - 同强度仅在 `fact_key` 相同且冲突可判定时允许覆盖。
  - LLM 来源（1-3）禁止执行对 `core` 的 `remove`。

### 6) 去重与冲突职责分离

- 精确去重：`normalized_content` 完全一致时合并强化计数。
- 近似去重：仅用于 recent 候选筛选；命中条件：同实例、同 `memory_type`、文本长度 `>=8`、`similarity >= 0.90`。
- `pg_trgm` 结果只作为“候选证据”，最终是否合并由规则层判定。

### 7) recent 归档触发时机

- 归档仅在写入链路触发，不在读取链路触发。
- 触发点：
  - `add/update/refresh_ids` 执行后
  - 模板复制到实例后
  - Admin 写入后
- 按 `utility_recent` 排序保留 active 集合，其余转 `status=2`。

### 8) 读取与预算（只读）

- 读取阶段仅执行排序与预算截断，不修改数据库状态。
- 预算：`memory_budget_tokens`，默认 `700`，软超 `+15%`。
- 顺序：先 `core` 再 `recent`。
- `core` 仅读取限量，不自动归档。

### 9) 指标与审计

- 指标：
  - `memory_dedup_merge_count`
  - `memory_conflict_detect_count`
  - `memory_conflict_override_count`
  - `memory_recent_archived_count`
  - `memory_prompt_tokens`
  - `memory_soft_budget_exceed_count`
- 审计事件：
  - 冲突覆盖
  - `core -> recent` 降级
  - 归档触发（含触发入口）

## 涉及文档与代码范围

- 方案文档：
  - `docs/plans/2026-05-07-ai-memory-forgetting-policy-fact-key.md`
- 规范文档（实施时同步更新）：
  - `docs/spec/ai/memory-system.md`
  - `docs/spec/ai/llm-interaction.md`
  - `docs/spec/ai/conversation-flow.md`
- 后端实现：
  - `backend/app/services/ai/memory/operations.py`
  - `backend/app/services/ai/memory/retrieval.py`
  - `backend/app/services/ai/memory/templates.py`
  - `backend/app/api/admin/ai_memory.py`
  - `backend/app/models/ai/memory.py`
  - `backend/alembic/versions/*.py`

## 验收标准

1. 实例记忆写入入口均通过 `memory_policy_service`，无旁路写入。
2. 读取链路保持只读，检索期间不产生归档写入。
3. active 集合满足 `normalized_content` 唯一；归档记录支持多版本留存。
4. `fact_key` 仅在固定槽位且命中置信规则时生成。
5. 低来源强度不能覆盖高来源强度，LLM 来源不能删除 `core`。
6. `pg_trgm` 仅用于 near-duplicate 候选筛选，不直接决定冲突覆盖。
7. `recent` 归档仅在写入链路触发，并完整产出归档审计事件。
