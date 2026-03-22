# 字数限制与业务失败消息链路落地方案（2026-03-21）

## 背景

- `system_configs.max_message_length_chars` 已存在于 required data（默认 49）。
- 当前长度限制存在硬编码（示例：`backend/app/schemas/ai/chat.py`），未接入统一消息入站链路。
- 客户端已支持通过 `CHAT_INFO.action.type=mark_message_failed` 标记指定 `msg_id_client` 的消息为失败（感叹号），并展示 `CHAT_INFO`。
- 业务失败需要做到：
  - 客户端不区分业务失败与发送失败：表现一致（感叹号标记失败 + chat_info）。
  - 多端一致：同一账号多端状态统一为失败。

## 目标

在统一消息入站链路中落地：

1. 消息字数超限失败。
2. 消息过频率失败。
3. 拉黑/非好友/实例 blocked 等业务拒收失败（更快反馈：前移到入站层）。

并打通服务端到客户端的“业务失败 → 标记失败（感叹号）+ chat_info”链路，同时满足幂等去重与多端一致性。

## 决策（已确定）

1. 业务失败的入站用户消息允许写入 `message_history`（用于幂等与多端一致）。
2. 业务失败的入站用户消息禁止写入 `ai_conversation_items`，禁止进入 buffer 聚合，禁止进入 LLM 链路。
3. 前端可比后端更严格（允许前端提前拦截），禁止出现“前端允许但后端拒绝”。
4. 服务端口径：以 Python `len()`（Unicode code point）计数，使用 `system_configs.max_message_length_chars` 作为服务端权威上限。

## 规范引用

本方案仅记录实施范围、接线点与验收标准；业务语义与字段规范以项目文档为准：

- `docs/spec/message/failure-handling.md`（失败分类与边界）
- `docs/spec/message/special-types.md`（CHAT_INFO + action 语义）
- `docs/spec/message/schema.md`（事件字段与 metadata 白名单）

## 失败反馈载体（服务端 → 客户端）

业务失败的客户端反馈统一通过时间线 `CHAT_INFO` 完成（包含 `action=mark_message_failed` 并指向原消息 `msg_id_client`）。

该消息结构与字段约束以项目规范为准，不在本方案文档重复定义：

- `docs/spec/message/special-types.md`（CHAT_INFO + action 语义）
- `docs/spec/message/schema.md`（事件字段与 metadata 白名单）

## 幂等去重与多端一致性

### 幂等去重（入站）

幂等键：`(conversation_id, msg_id_client)`，由 `message_history` 的唯一约束提供：

- `uq_message_history_conv_client_id UNIQUE (conversation_id, msg_id_client)`

重复入站处理规则：

- 若已存在该入站消息记录：不重复写入用户消息，不重复触发 buffer/LLM。

### 多端一致性（fanout）

业务失败路径必须将以下两条时间线消息都写入并 fanout：

1. 用户 TEXT（含 `msg_id_client`）。
2. CHAT_INFO（含 `action.target_msg_id=msg_id_client`）。

客户端收到 CHAT_INFO 后即可在所有端统一将对应消息标记为 FAILED。

顺序约束：

- 目标是“先投递用户 TEXT，再投递 CHAT_INFO”，避免客户端先收到失败指令时找不到目标消息。

## 接线点（服务端）

### 统一入站业务层（核心）

`backend/app/services/message/inbound/router.py:route_message`

新增/调整职责：

1. 生成 `msg_id_server`（保持现状）。
2. 写入 `message_history`（保持现状）。
3. 在写入后、进入 buffer 前执行业务失败判定（新增）：
   - TEXT 长度校验：`system_configs.max_message_length_chars`
   - 业务频控：复用 `backend/app/services/security/rate_limiter.py` 的 message rate limit 配置
   - 联系人/实例权限校验：复用 `MessageValidationService`（拉黑/实例 blocked/非好友）
4. 若命中业务失败：
   - 写入并 fanout CHAT_INFO（含 `action=mark_message_failed`）
   - 不调用 `buffer.add_message_to_buffer`
   - 不进入后续 AI 编排

### WebSocket 入站

`backend/app/api/ws/messages.py`

- 保持 `ack` 的耐久性语义：在 `route_message` 成功写入 `message_history` 并提交后返回 `ack`（包含 `msg_id_server`）。
- 业务失败反馈通过时间线的 CHAT_INFO 推送完成（多端一致）。

### LeanCloud webhook 入站

`backend/app/api/v1/webhook.py`

- webhook 必须返回 200。
- 业务失败不抛异常中断 webhook；由 `route_message` 内部完成 chat_info 写入与 fanout。

## 配置项

1) 字数限制：

- `system_configs.max_message_length_chars`（整数）

2) 消息频控（已存在 required data）：

- `message_rate_limit_short_requests`（默认 5）
- `message_rate_limit_short_window_seconds`（默认 10）
- `message_rate_limit_long_requests`（默认 20）
- `message_rate_limit_long_window_seconds`（默认 60）

## 验收标准

### 字数超限

- 前端输入拦截可提前发生；若仍到达服务端，服务端以 `max_message_length_chars` 拒绝且不截断。
- 服务端写入用户 TEXT 到 `message_history`。
- 服务端写入并 fanout CHAT_INFO（含 `mark_message_failed` 指向 `msg_id_client`）。
- 服务端不写 `ai_conversation_items`，不创建/更新 buffer，不触发 LLM。
- 客户端将该条用户消息标记为 FAILED（感叹号），并展示 chat_info。
- 多端同时在线时，所有端对同一 `msg_id_client` 统一标记失败。

### 频控超限

- 服务端按配置命中频控时走同样的失败路径。
- CHAT_INFO 携带 `retry_after_seconds`（若可计算），客户端可按需展示“请稍后再试”。

### 权限拒收（拉黑/非好友/实例 blocked）

- 服务端在入站层命中拒收后走统一失败路径。
- 不进入 AI 编排，不污染上下文。

### 通用约束

- 不存在静默截断、默认兜底或向后兼容分支。
- 错误/失败原因分支不得依赖 `content` 文案；仅依赖 `reason` 等机器字段。

## 实施状态

- 方案已确定，待进入实施阶段落地代码与文档对齐。
