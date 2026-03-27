# 2026-03-26 Memory Refresh ID 化 + 阈值告警（通用业务告警事件表）落库方案

## 已确认决策

- refresh 协议形态：`memory_operations.refresh_ids: string[]`（digits-only，服务端归一化后转 int）。
- 告警阈值策略（常量）：`refresh_total >= 2` 且 `refresh_miss_ratio_bp >= 5000` 触发告警（不通过 `system_configs` 配置）。
- 阈值超限后的执行策略：仅告警，不阻断本轮 memory side-effect。
- 告警落库粒度：每轮会话最多一条汇总告警。
- 告警落库表：通用业务告警事件表 `alert_events` 与实体关联表 `alert_event_entities`。
- 告警保留周期：默认 30 天（由 `alerting_default_retention_days` 控制）。
- 告警清理配置：走 `system_configs`；阈值与开关为常量。
- 告警事件类型：`event_type = MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED`，`domain = ai_memory`。
- 严重程度：`severity_level = 30`（WARNING；使用 Python logging level 数值，允许：10/20/30/40/50；其中 10 为 DEBUG 可选）。
- details 约束：必须包含 `schema_version`；大小限制 16KB；禁止写入用户原文消息，只记录 ID/计数/样本。
- 告警去重语义：`(event_type, dedupe_key)`；`dedupe_key` 由产生方生成；空值表示不去重。
- 清理方式：后台定时任务清理，不在写入路径执行清理。
- 通知体系：本次不实现。

## 背景问题

- 当前 `refresh` 依赖 `content` 精确匹配，LLM 在摘要改写后容易出现未命中。
- 未命中行为目前仅记录 WARNING，缺少结构化告警记录，无法形成稳定的运营追踪。
- 目标是将 `refresh` 从文本匹配收敛为 ID 匹配，消除语义漂移导致的误差，并引入阈值告警闭环。

## 目标

- `refresh` 执行基于 `memory_id`，不再基于文本内容匹配。
- Prompt 与 Schema 强制约束 LLM 仅可从候选记忆 ID 集合中选择 refresh 目标。
- 对 refresh 未命中建立结构化告警记录，并按 30 天保留策略自动清理。
- 运行时行为保持：消息发送链路不因 refresh 告警而中断。

## 方案设计

### 1) LLM 协议收敛（refresh_ids）

- `memory_operations` 结构调整为：`remove`、`update`、`refresh_ids`、`add`。
- `refresh_ids` 类型为 `string[]`，元素为 `ai_instance_memories.id` 的十进制字符串（digits-only）。
- 旧字段 `refresh`（string[]）在本次实施后不再接受，不做向后兼容分支。

#### refresh_ids 归一化口径（服务端）

- 输入：LLM 原始 `refresh_ids: string[]`。
- 过滤与转换：
  - 仅保留非空字符串。
  - 仅保留 digits-only（`^[0-9]+$`）项。
  - 将通过校验的字符串转为 int（memory_id）。
  - 去重（保持原始顺序）。
  - 截断：每轮最多 2 条（与 prompt 约束一致）。
- 归一化后输出：`refresh_ids_normalized: list[int]`（仅用于执行与统计，不回写给 LLM）。

### 2) Prompt 约束强化

- System prompt 的记忆上下文输出必须携带 memory id（例如每条记忆明确展示 `id` 与 `content`）。
- Prompt 明确约束：
  - `refresh_ids` 只能从当前轮提供的候选 memory id 中选择。
  - 禁止使用自由文本做 refresh。
  - 每轮 refresh 数量控制为 1-2 条。
  - 禁止在 `outgoing_messages` / `followup_messages` 中提及 memory id 或任何内部字段名（仅用于内部操作，不面向用户）。

#### refresh 候选集合口径（用于 prompt 展示）

- 仅展示“可刷新记忆”候选集合（recent memories）：
  - `ai_instance_memories.status = 1`
  - `ai_instance_memories.memory_type = 'recent'`
  - `ai_instance_memories.expires_at IS NULL OR expires_at > now()`
- core memories 不纳入 refresh 候选集合（core 不需要续期）。

### 3) 运行时执行逻辑

- `normalize_memory_operations` 改为解析 `refresh_ids`（string[]），并按“归一化口径”输出 `refresh_ids: list[int]`（用于执行与统计，不再传播原始字符串）。
- `process_memory_operations` / `_apply_refresh` 改为按 `(instance_id, memory_id, status=1, memory_type='recent')` 查询并更新：
  - 命中：更新 `refreshed_at` 并重算 `expires_at`。
  - 未命中：记录单项 miss（用于本轮统计），不抛异常。
- 每轮 memory side-effect 产出 refresh 统计（基于“归一化后最终尝试执行的 refresh_ids 集合”）：
  - `refresh_total`
  - `refresh_miss`
  - `refresh_miss_ratio`
  - `refresh_miss_ratio_bp`（0-10000，落库使用该值）。

### 4) 阈值告警（不阻断）

- 判定条件：`refresh_total >= threshold_total` 且 `refresh_miss_ratio_bp >= threshold_ratio_bp`。
- 触发后：
  - 记录结构化日志事件 `memory_refresh_miss_threshold_exceeded`。
  - 写入通用业务告警事件表一条汇总记录（`event_type = MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED`）。
- 不触发行为变更：不回滚、不跳过 memory side-effect、不影响消息发送。

#### 事件落库口径（本次告警）

- `alert_events.event_type = MEMORY_REFRESH_MISS_THRESHOLD_EXCEEDED`
- `alert_events.domain = ai_memory`
- `alert_events.severity_level = 30`
- `alert_events.dedupe_key = instance_id=<instance_id>|task_turn_version=<task_turn_version>`
- `alert_event_entities` 关联实体（至少包含以下两条）：
  - `entity_type = ai_instance`，`entity_id = <instance_id>`
  - `entity_type = user`，`entity_id = <user_id>`

#### 非阻断事务语义（告警写入/清理）

- memory side-effect（remove/update/refresh/add）提交不受告警写入失败影响。
- 告警写入使用独立事务（或独立 session），best-effort：
  - 成功：落库并记录 INFO。
  - 失败：仅记录 ERROR，不影响主链路提交与消息发送。
- 告警清理通过后台定时任务执行，不影响主链路。

### 5) 业务告警基础设施（通用）

- 子系统规则与边界：`docs/spec/alerting.md`
- 表结构与索引/约束：`docs/data-dict/alerting.md`

#### details(JSONB) 口径（本次告警）

- `schema_version`：details schema 版本（int）。
- `refresh_ids_raw_sample`：原始 refresh_ids 字符串样本（最多前 10 个）。
- `refresh_ids_normalized`：归一化后参与执行的 memory_id 列表。
- `hit_ids`：命中列表。
- `miss_ids`：未命中列表。
- `invalid_id_count`：非法 ID 数量（非 digits-only、空串等）。
- `duplicates_dropped_count`：去重丢弃数量。
- `candidate_recent_ids_sample`：候选 recent memory_id 样本（最多 10 个）。
- `candidate_recent_count`：候选 recent 总数。

### 6) 配置项（system_configs，仅告警清理）

- 告警基础设施（全局）：
  - `alerting_cleanup_enabled`（bool，默认 true）
  - `alerting_cleanup_interval_seconds`（int，默认 3600）
  - `alerting_default_retention_days`（int，默认 30）

- 本次告警规则（AI memory refresh miss）使用常量，不通过 `system_configs` 配置：
  - `enabled = true`
  - `threshold_total = 2`
  - `threshold_ratio_bp = 5000`

#### 阈值读取口径（服务端）

- 本次阈值为常量，不做运行时读取。

### 7) 30 天保留清理

- 通过后台定时任务清理：
  - 清理条件：`alert_events.created_at < now() - retention_days`。
  - `retention_days` 读取自 `alerting_default_retention_days`。
  - 清理失败仅记录 ERROR，不影响主链路。
- 多进程场景下使用 PostgreSQL advisory lock，避免重复清理。

## 代码改动范围

- `backend/app/services/ai/response_schema.py`
- `backend/app/services/ai/utils/normalization.py`
- `backend/app/services/ai/memory/operations.py`
- `backend/app/services/ai/memory/retrieval.py`（记忆上下文含 ID，输出 refresh 候选）
- `backend/app/services/ai/orchestrators/llm_response_handler.py`
- `backend/app/services/ai/conversation_prompt.py`（记忆上下文含 ID）
- `backend/app/services/ai/utils/min_contract.py`
- `backend/app/services/ai/orchestrators/conversation_flow.py`
- `backend/app/services/system_config.py`（告警配置读取）
- `backend/app/enums/system.py`（新增告警事件相关枚举）
- `backend/app/models/system/*`（新增 `alert_events` / `alert_event_entities` 模型）
- `backend/app/crud/system/*`（告警事件写入与清理）
- `backend/alembic/versions/*`（新增表迁移）
- `backend/database/init/sql/01_schema.sql`（新增告警表）
- `backend/database/init/sql/02_required_data*.sql`（新增配置键）

## 文档同步范围（实施完成后）

- `docs/spec/alerting.md`
- `docs/spec/ai/memory-system.md`
- `docs/spec/ai/llm-interaction.md`
- `docs/spec/ai/conversation-flow.md`
- `docs/data-dict/alerting.md`
- `docs/data-dict/*`（从 AI 数据字典中移除告警表内容）

## 实施任务

1. 调整 `memory_operations` Schema，移除 `refresh`，新增 `refresh_ids`。
2. 调整记忆上下文渲染，输出可用于 refresh 的 memory id。
3. 调整归一化逻辑与内存操作执行逻辑，改为 ID 命中。
4. 在 memory side-effect 路径计算 refresh miss 统计并产生日志事件。
5. 新增通用业务告警事件表 `alert_events` 与 `alert_event_entities`，并接入写入与去重。
6. 新增告警配置键并接线读取校验（缺失/类型错误 fail-fast）。
7. 实现后台定时任务清理（全局清理 `alert_events`）。
8. 完成 Alembic、init SQL、数据字典同步。
9. 补充测试（Schema、执行、告警触发、去重、保留清理、无阻断语义）。

## 验收标准

- `memory_operations.refresh_ids` 可稳定驱动 refresh，且不依赖 content 精确匹配。
- LLM 输出非法 refresh 内容时被归一化剔除，不影响消息发送主链路。
- 阈值命中时必定同时产生结构化日志与通用业务告警事件表记录。
- 告警事件记录粒度为每轮汇总，不出现单轮重复多条（按 `(event_type, dedupe_key)` 去重）。
- 告警清理生效：超过 `retention_days` 的历史记录被删除。
- 所有新配置键在 `system_configs`、init SQL、数据字典中一致。
- 相关测试通过，且不引入 `type: ignore` / `noqa` 补丁式规避。
