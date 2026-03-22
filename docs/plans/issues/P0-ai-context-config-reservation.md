# AI 上下文配置预留（2026-03-21）

## 背景

文档已描述从 `system_configs` 获取上下文条数限制与时间窗口：

- `docs/spec/message/context.md`
- `docs/spec/ai/prompt-building.md`

当前 required data 未包含上述 key，调用方存在不限制条数的调用方式。

## 目标

记录配置项与预留接线点，不在本次任务中实施。

## 预留配置项

- `ai_context_max_messages`：上下文消息条数上限（int）
- `ai_context_time_window_days`：上下文时间窗口（天，int）

## 预留接线点

- 调用方：`backend/app/services/ai/orchestrators/conversation_flow.py`
  - 从 `system_configs` 读取 `ai_context_max_messages` 并传入 `build_conversation_context(..., max_context_length=...)`
- 查询层：`backend/app/services/ai/queries/conversation_queries.py`
  - 增加按 `created_at` 的时间窗口过滤（`ai_context_time_window_days`）

## 行为约束（预留）

- 配置缺失或非法：视为系统配置异常，不使用默认兜底
- 不允许在调用层悄悄回退到默认 20/30

## 验收标准（预留）

- 上下文条数限制与时间窗口过滤按配置生效
- 配置变更后在所有实例一致生效（缓存一致性明确）

## 状态

- 未实施
