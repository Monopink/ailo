# AI 会话上下文策略配置（2026-05-06）

## 背景

AI 对话上下文来源于 `ai_conversation_items`，当前对话链路需要按配置控制：

- `docs/spec/message/context.md`
- `docs/spec/ai/prompt-building.md`

当前 `system_configs` 未包含会话上下文策略配置，调用方会进入不限制条数的上下文构建流程。

## 已确认决议

- 配置缺失或非法时，本轮 AI 处理静默失败
- 非配置类异常不归类为配置异常，按系统故障路径处理
- 用户侧不返回错误提示；管理员与开发侧必须有日志、审计与告警可观测性
- 上下文策略采用最终一致，配置变更后 `<= 5s` 在所有实例生效
- 时间窗口采用滑动窗口，按 `now - N*24h` 计算
- 多实例架构直接落地，不保留单机特化处理
- 迁移冲突时覆盖 `ai_conversation_context_max_messages` 与 `ai_conversation_context_time_window_days` 的配置值

## 目标

为 `ai_conversation_items` 上下文构建接入可运维的配置策略，并保证多实例一致性。

## 配置项

- `ai_conversation_context_max_messages`：上下文消息条数上限（int）
- `ai_conversation_context_time_window_days`：上下文时间窗口（天，int）

## 实施范围

- 配置读取与缓存一致性：`backend/app/services/system_config.py`
- 对话编排接线：`backend/app/services/ai/orchestrators/conversation_flow.py`
- 上下文查询：`backend/app/services/ai/queries/conversation_queries.py`
- 上下文构建：`backend/app/services/ai/conversation_prompt.py`
- 静默失败收口：`backend/app/services/message/processing/scanner.py`
- 配置种子与迁移：`backend/database/bootstrap/base.sql`、`backend/alembic/versions/*.py`
- 规范文档同步：`docs/spec/message/context.md`、`docs/spec/ai/prompt-building.md`、`docs/spec/ai/conversation-flow.md`

## 实施结果

- 上下文条数限制由 `ai_conversation_context_max_messages` 控制
- 上下文时间窗由 `ai_conversation_context_time_window_days` 控制
- 配置异常记录日志并触发审计落库
- 本轮处理静默失败，不向用户侧返回错误提示
- 非配置类异常按系统故障路径记录并触发告警
- 配置缓存支持多实例最终一致刷新

## 验收标准

- 上下文条数限制与时间窗口过滤按配置生效
- 配置变更后所有实例在 5 秒内生效
- 配置缺失或非法时，系统记录错误并静默结束本轮处理
- 非配置类异常按系统故障分类记录与告警，不归类为配置异常

## 状态

- 实施中
