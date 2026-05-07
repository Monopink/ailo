# 会话记录归档（ai_conversation_items）

## 目标

- 控制 `ai_conversation_items` 热表规模。
- 归档执行不进入实时对话主链路。
- 历史消息完整落入 `ai_conversation_items_archive` 供审计查询。

## 架构定义

### 分层职责

- 调度层（`deployment/prod/systemd/*`）：按固定周期触发归档任务。
- 执行层（`backend/app/services/ai/*` + backend 命令入口）：执行归档选择、迁移、删除、监控记录。
- 配置层（`system_configs`）：提供归档参数。

### 触发链路

- `systemd timer` 每 5 分钟触发一次归档。
- `systemd service` 仅调用 backend 归档命令入口，不承载业务 SQL。
- 归档任务在数据库侧使用单任务锁，禁止并发执行。

## 归档规则

### 维度

- 会话维度：`(user_qiao_id, instance_qiao_id)`。

### 候选条件

- 时间条件：`created_at < now - retention_days`。
- 溢出条件：按 `created_at DESC, id DESC` 排序后 `rn > keep_recent_count`。

### 保留约束

- 每会话热表保留条数为硬约束：归档后剩余记录数必须 `>= keep_recent_count`。

### 执行方式

- 使用批量 SQL 处理候选集。
- 单轮处理上限为 `batch_size`。
- 同一事务内完成“写入归档表 + 删除热表”。
- 归档表保留原始 `id`，用于幂等去重与审计追溯。
- 出现归档表冲突（同 `id` 已存在）时，仍需删除热表对应记录。

## 配置键（system_configs）

- `ai_conversation_archive_enabled`（bool）
- `ai_conversation_archive_retention_days`（int）
- `ai_conversation_archive_keep_recent_count`（int）
- `ai_conversation_archive_batch_size`（int）

## 可观测性

### 成功指标

- `scan_sessions_count`
- `candidates_count`
- `archived_count`
- `deleted_count`
- `duration_ms`
- `last_success_at`

### 失败指标

- `failure_reason`
- `failed_at`

### 告警

- 归档任务失败接入现有告警链路。

## 实施清单

1. 新增 backend 归档执行服务与命令入口。
2. 删除部署脚本中的归档业务逻辑，仅保留调度调用。
3. 归档 SQL 实现批量、事务原子、冲突幂等删除。
4. 归档任务接入并发锁与指标日志。
5. `system_configs` 使用新配置键，移除旧配置键读取。
6. 同步文档：`docs/spec/message/context.md`。

## 验收标准

- 对话主链路不触发归档执行。
- 定时调度稳定触发，且同一时刻只有一个归档任务执行。
- 归档任务按配置键生效并输出完整指标。
- 归档表可按 `id` 与会话维度追溯历史消息。
