# Task: WS 出站失败域隔离与发送可恢复性修复方案（单队列，2026-02-25）

## 1. 问题与触发样本

本任务处理 Chat Console 在 staging 环境的“用户消息入库成功，但 AI 不回复”问题。

触发样本：

1. 样本一：`message_history.id=285027913806516224`，`msg_id_server=msg_285027913802321920`
   - 入站路由成功
   - 扫描阶段报错：`instance_not_found_for_relationship_config`
2. 样本二：`msg_id_server=msg_285035929851269120`
   - 入站路由成功，AI 处理成功，`conversation_processing_completed`
   - 发送阶段报错：`Failed to send realtime message: LeanCloud configuration incomplete`

## 2. 本任务范围

1. 修复 typing 失败阻断 timeline 正文发送
2. 修复 finalize 时序，消除“buffer 已完成但首条正文无恢复入口”窗口
3. 保持现有 `message_dispatch_outbox` 单队列恢复架构

本任务不包含：

1. 新增 `ai_send_intents` 表
2. `memory/score` 副作用恢复编排
3. 样本一根因治理（独立任务处理）

## 3. 最终决策

### D1. 恢复入口采用单队列

1. timeline 恢复入口统一为 `message_dispatch_outbox`
2. 不新增 `ai_send_intents`
3. outbox worker 继续承担重试与恢复职责

### D2. Typing 采用 provider-aware realtime fanout

1. `typing_start/typing_end` 为 realtime best-effort 事件
2. typing 失败仅记录日志，不抛出阻断主流程异常
3. 按活跃 endpoint 的 `provider` 扇出
4. provider 不支持 typing 时记录 `typing_unsupported_provider` 并跳过
5. typing 不写 `message_history`、`message_dispatch_outbox`、`message_deliveries`

### D3. 首条 assistant 文本门槛

当 `should_reply=true` 且存在 assistant 文本发送时，首条 assistant 文本必须在同一事务内完成：

1. 写入 `message_history`
2. 写入 `message_dispatch_outbox`
3. 写入 `ai_conversation_items`
4. 执行 `finalize_buffer_if_locked(... -> COMPLETE)`

## 4. 发送状态机与事务边界

### 4.1 `process_llm_response` 阶段

1. 保存安全副作用与请求日志
2. 不执行发送前 finalize
3. 触发异步发送执行器

### 4.2 发送执行器阶段

1. 每条 assistant 文本发送前执行 `typing_start`（best-effort）
2. timeline 主路径执行 `message_history + outbox + conversation_item`
3. 首条 assistant 文本满足门槛后，在同一事务内 finalize buffer
4. 首条门槛未达成的失败/抢占，buffer 终态为 `CANCELLED`

### 4.3 恢复语义

1. timeline 失败恢复入口仅为 outbox
2. outbox 重试按 endpoint 粒度恢复
3. typing realtime 失败不进入 outbox

## 5. 发送编排重构

### 5.1 API 边界拆分

1. `send_timeline_message(...)`：只处理 timeline（入库 + outbox）
2. `fanout_realtime_typing_best_effort(...)`：只处理 typing realtime fanout

### 5.2 typing 执行顺序

1. 每条 assistant 文本发送前发 `typing_start`
2. typing 等待期间执行抢占检查
3. 文本进入 timeline 主路径
4. typing 失败不改变 timeline 处理分支

## 6. 实施拆解

### 阶段 1：发送链路修复

1. 重构 `backend/app/services/message/outbound/sender.py`，拆分 timeline 与 typing 路径
2. 移除 typing 路径默认 provider 依赖
3. 重构 `backend/app/services/message/dispatch/realtime.py`，按 endpoint.provider 扇出并内部吞异常

### 阶段 2：事务时序修复

1. 调整 `backend/app/services/ai/orchestrators/llm_response_handler.py`，移除发送前 finalize
2. 调整 `backend/app/services/message/processing/sender.py`，首条 assistant 文本在同事务内完成门槛与 finalize

### 阶段 3：文档同步

1. `docs/spec/ai/message-sending.md`
2. `docs/spec/message/failure-handling.md`
3. `docs/spec/message/typing.md`
4. `docs/data-dict/ai-conversation.md`
5. `docs/data-dict/message.md`

## 7. 验证与回归

1. WS 在线 + LeanCloud 不可用：typing 失败不阻断 timeline
2. 单 endpoint 失败：同消息其他 endpoint 不受影响
3. outbox 重试仅重试失败 endpoint，已成功 endpoint 不重复投递
4. 首条正文持久化前失败：buffer 不进入 `COMPLETE`
5. 首条正文持久化后中断：`buffer=COMPLETE` 且 outbox 可恢复

## 8. 验收标准

1. LeanCloud 配置缺失时，assistant timeline 文本仍可入 `message_history/outbox`
2. typing 失败只记日志，不触发发送任务异常退出
3. `should_reply=true` 且存在 assistant 文本发送时，`buffer=COMPLETE` 前首条正文必须已写入 outbox
4. 同一 timeline 消息满足“部分失败可重试、整体不中断”
5. 不再出现“AI 处理完成但正文不可见且无恢复入口（首条）”
6. 不再存在 typing 默认 provider 隐式依赖
