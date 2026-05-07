# 全域关键告警模块实施计划（统一事件采集与落库）

## 问题点

1. 关键故障在多个链路中仅有日志，未统一沉淀为可检索、可聚合、可闭环的业务告警事件。
2. 不同模块缺少统一告警写入入口，`details` 结构、实体关联与去重口径不一致。
3. 现有告警枚举覆盖范围不足，无法支撑全域关键告警治理。
4. 仅使用永久去重会遮蔽持续性故障，无法体现故障跨日延续性。

## 需求点

1. 建立全域关键告警覆盖能力，统一写入 `alert_events` 与 `alert_event_entities`。
2. 告警写入必须不阻断业务主流程，保持 best-effort。
3. 告警事件必须具备稳定契约：统一字段、统一分级、统一去重、统一实体关联。
4. 告警模块仅负责事件定义、采集、落库与检索一致性，不包含通知通道建设。

## 已拍板决策（固定）

1. 覆盖范围：AI 对话 + message dispatch + background worker。
2. 去重策略：按天时间桶去重。
3. `details` 约束：业务告警必须非空且包含 `schema_version`。
4. 实体关联：同时关联 qiao_id、内部 ID、`buffer_id`（有值时）。
5. 写入策略：独立 session best-effort，不与主事务强耦合。
6. 严重级别：由中央映射表统一管理，调用方不得自行散落定义。
7. 错误码：统一 `error_code` 字典，禁止直接使用异常类名作为最终事件码。
8. 保留策略：按严重级别分层 retention，`CRITICAL` 保留周期高于其他级别。

## 本次实施边界

1. 本次仅实施告警模块能力，不改造通知子系统。
2. 本次不引入外部告警框架作为主存储与主规则引擎。
3. 本次不变更 `alert_events`/`alert_event_entities` 的审计追加写语义。

## 实施方案

### 1) 统一告警写入入口

- 新增统一入口服务：`backend/app/services/alerting/events.py`。
- 业务模块仅通过 `emit_alert(...)` 写入，禁止直接调用 `crud.system.alerting`。
- `emit_alert(...)` 固定执行：
  - `details` 契约校验（必含 `schema_version`）
  - 字段白名单与敏感信息清理
  - 去重键构造（含日桶）
  - 实体关联规范化
  - 独立 session 落库与异常吞吐日志

### 2) 告警域与事件类型扩展

- 扩展 `AlertDomain`：
  - `ai_conversation`
  - `message_dispatch`
  - `background_worker`
  - `system_config`
  - `security`
- 扩展 `AlertEventType`：为每个域定义关键故障事件类型，事件名称采用稳定常量命名。
- 扩展 `AlertEntityType`：补齐 `ai_message_buffer` 等关键实体类型。

### 3) 去重与分级规则固化

- dedupe_key 固定由“事件特征键 + UTC 日期桶（YYYY-MM-DD）”构成。
- 配置类异常键：`instance_qiao_id + config_key + error_code + date_bucket`。
- 系统故障键：`instance_qiao_id + error_class + error_code + date_bucket`。
- `severity_level` 通过中央映射表生成，禁止调用方透传任意等级。

### 4) 关键链路接入

- AI 对话链路：
  - `conversation_flow.py` 配置异常分支接入告警。
  - `conversation_flow.py` 非配置系统故障分支接入告警。
- message dispatch 链路：
  - `dispatch/worker.py` 任务失败、重试耗尽等关键分支接入告警。
- background worker 链路：
  - `scanner.py` 与其他后台 worker 的关键故障分支接入告警。

### 5) retention 分层清理

- 在清理任务中按 `severity_level` 应用分层保留天数。
- 保留配置来源统一归属 `system_configs`（alerting 组），由清理 worker 读取执行。

## 文档与代码范围

- 方案文档：
  - `docs/plans/2026-05-07-alerting-key-events-foundation.md`
- 规范文档（实施时同步更新）：
  - `docs/spec/alerting.md`
  - `docs/spec/ai/conversation-flow.md`
- 后端实现：
  - `backend/app/services/alerting/events.py`（新增）
  - `backend/app/enums/system.py`
  - `backend/app/crud/system/alerting.py`
  - `backend/app/services/ai/orchestrators/conversation_flow.py`
  - `backend/app/services/message/dispatch/worker.py`
  - `backend/app/services/message/processing/scanner.py`
  - `backend/app/services/alerting/cleanup.py`
  - `backend/tests/*`（告警模块与接入链路测试）

## 验收标准

1. 三大域（AI 对话、message dispatch、background worker）关键故障均可在 `alert_events` 检索到对应事件。
2. 告警写入失败不会阻断业务主流程，失败路径有结构化错误日志。
3. 所有新增业务告警 `details` 均非空且包含 `schema_version`。
4. 告警实体可同时按 qiao_id、内部 ID、`buffer_id`（有值）完成关联查询。
5. 去重策略按天生效，跨天持续故障可产生新事件。
6. 告警严重级别由中央映射统一输出，不存在调用方自定义漂移。
7. retention 按严重级别分层生效，清理流程可重复执行且结果稳定。

## 状态

- 未开始
