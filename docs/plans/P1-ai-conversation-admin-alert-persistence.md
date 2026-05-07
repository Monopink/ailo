# AI 对话管理员告警事件落库

## 背景状态（2026-05-07）

- `docs/spec/ai/conversation-flow.md` 已要求：
  - 配置类异常静默结束用户侧流程
  - 管理员与开发侧需要可观测告警
- 当前链路已具备日志与审计落库，但未将该类事件写入 `alert_events`。
- `docs/spec/alerting.md` 已定义统一告警落库模型与清理机制，可直接复用。

## 问题定义

- AI 对话链路的配置异常与系统故障缺少统一业务告警事件，管理员侧无法在告警域进行检索、聚合与闭环跟踪。
- 仅依赖日志与审计日志时，跨实例聚合和运营检索成本高。

## 目标

- 为 AI 对话链路建立管理员告警事件落库能力，统一写入 `alert_events` 与 `alert_event_entities`。
- 保持用户侧无感知，不向用户返回内部错误。
- 告警写入采用 best-effort，不阻断主流程收敛。

## 告警事件范围

- 配置类异常事件：`ai_conversation_context_max_messages` / `ai_conversation_context_time_window_days` 缺失、类型非法、取值越界。
- 非配置类系统故障事件：AI 对话主流程中的非业务异常（数据库异常、依赖异常、运行时异常）。

## 落库契约

- 事件模型遵循 `docs/spec/alerting.md`：
  - 写入表：`alert_events`、`alert_event_entities`
  - `details` 必含 `schema_version`
  - `details` 序列化大小不超过 16KB
  - 不写入用户原文消息
- 实体关联至少包含：
  - `instance_qiao_id`
  - `user_qiao_id`
  - `buffer_id`（有值时）
- 去重规则：
  - 配置类异常按 `instance_qiao_id + config_key + error_code` 去重
  - 系统故障按 `instance_qiao_id + error_class + error_code` 去重

## 实施范围

- `backend/app/services/ai/orchestrators/conversation_flow.py`
- `backend/app/services/message/processing/scanner.py`
- `backend/app/services/ai/*`（如新增专用告警写入模块）
- `backend/app/enums/system.py`（如需新增 `AlertEventType`）
- `backend/tests/*`（补充告警写入与不阻断主流程的测试）
- `docs/spec/ai/conversation-flow.md`（仅在实现口径变化时同步）

## 非范围

- 告警通知通道（邮件、IM、短信）接入
- 告警看板与管理后台筛选页面改造
- 全量历史错误日志回填为告警事件

## 验收标准

- 配置类异常触发时，用户侧保持无感知，且生成对应 `alert_events` 记录。
- 非配置类异常触发时，生成对应 `alert_events` 记录，且不被归类为配置异常。
- 告警写入失败不阻断主流程，错误日志包含失败上下文。
- 新增测试覆盖：
  - 配置类异常告警写入
  - 非配置类异常告警写入
  - 告警写入失败不影响主流程收敛

## 状态

- 未开始
