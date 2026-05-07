# 业务告警（Alerting）

本文档定义业务告警子系统的规则与边界。业务告警用于记录“需要闭环处理/需要跨天追踪/需要运营检索”的业务事件，不用于存储所有异常与错误日志。

## 职责边界

- 本文档：告警事件的语义、去重、严重程度、details 约束、清理机制与配置来源。
- 涉及数据表：`alert_events`, `alert_event_entities`。
- 具体业务规则（例如 AI 记忆 refresh miss）：由各子系统实现并写入对应 `event_type`，不在本文件描述其阈值细节。

## 事件模型

系统以“告警事件（alert event）”作为唯一落库载体：

- 表：`alert_events` + `alert_event_entities`
- 事件以追加写（audit-only）方式记录；去重冲突时不更新既有事件。
- 关键业务告警统一通过告警模块入口写入，调用方不直接拼装持久化字段。

### 关键字段

- `event_type`：事件类型（enum: `AlertEventType`，来源：`backend/app/enums/system.py`）。
- `domain`：业务域（enum: `AlertDomain`，来源：`backend/app/enums/system.py`）。
- `severity_level`：严重程度（enum: `AlertSeverityLevel`，与 Python logging level 对齐，允许：10/20/30/40/50）。
- `dedupe_key`：去重键（可为空）；非空时参与去重。
- `details`：JSONB 详情（关键业务告警必填）；用于诊断与运营检索。

## 去重语义

- 去重键为：`(event_type, dedupe_key)`。
- `dedupe_key` 由产生方生成，用于表达“同一去重桶（bucket）”内只写入一条事件。
- 关键业务告警的 `dedupe_key` 必须包含 UTC 日期桶（`YYYY-MM-DD`）。
- `dedupe_key` 为空表示该事件不去重。
- 去重冲突时写入行为为 `DO NOTHING`（不更新既有事件，保持审计语义）。

## details 约束

- `details` 必须包含 `schema_version`（int）。
- `details` 大小上限：16KB（序列化后）。
- `details` 禁止写入用户原文消息，只记录 ID/计数/样本（例如 memory_id 样本、候选集数量、非法输入计数等）。

## 实体关联

通过 `alert_event_entities` 将事件关联到业务实体：

- `entity_type`（enum: `AlertEntityType`）+ `entity_id`（string）
- `entity_id` 统一承载 bigint/uuid/qiao_id，禁止在该字段内混入结构化 JSON。
- 关键业务告警至少关联实例、用户与处理窗口实体（窗口存在时）。

## 清理机制

告警事件由后台定时任务清理（不在写入路径执行清理）：

- 清理条件：`alert_events.created_at < now() - retention_days`
- 多进程场景下使用 PostgreSQL advisory lock，避免重复清理
- retention_days 按 `severity_level` 分层配置读取。

### system_configs（全局）

告警清理由 `system_configs` 提供全局配置（group_name=`alerting`）：

- `alerting_cleanup_enabled`（bool）
- `alerting_cleanup_interval_seconds`（int）
- `alerting_default_retention_days`（int）
- `alerting_retention_days_debug`（int）
- `alerting_retention_days_info`（int）
- `alerting_retention_days_warning`（int）
- `alerting_retention_days_error`（int）
- `alerting_retention_days_critical`（int）
