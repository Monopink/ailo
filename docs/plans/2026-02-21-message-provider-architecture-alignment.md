# Task: 消息 Provider 工厂与 WebSocket 架构对齐（2026-02-21）

## 背景

基于任务 `2026-02-10-test-websocket-provider.md` 的落地结果，当前实现已具备 WebSocket 通道能力，但仍存在：

1) Provider 工厂仍是“单默认 Provider”模型，无法支持多 endpoint / 多 provider 并存。
2) 广播逻辑分散在 API 与 processing 层，不在统一业务编排点。
3) 入站后 fanout 未统一，LeanCloud 入站与 WS 入站行为不一致。
4) `target_key` 虽已落表，但 provider 边界与业务边界未对齐。
5) 发送链路存在“先发后记/已落库未派发”时间窗，故障恢复能力不足。

---

## 本任务宗旨

- 架构正确性优先于最小改动
- 不做向后兼容兜底，不允许静默 fallback
- 仅增加必要抽象，不引入厚平台层

---

## 最终目标

1) `target_key` 的生成/校验/使用由 Provider 内部负责。
2) “发给谁、是否发、投递记录落库”统一在业务层执行。
3) 工厂从“默认 Provider”升级为“按 endpoint.provider 解析发送器”。
4) WebSocket 与 LeanCloud 遵守同一 dispatch 契约。
5) 时间线消息采用 Outbox 派发，保证可恢复与一致性。
6) `message_endpoints` 支持 USER/DEVICE 两种投递粒度，禁止强行统一所有 provider 为同一粒度。

---

## 架构决策（最终）

### D1. 分层职责

- API 层：协议接入（鉴权、帧级协议校验、连接生命周期），不做 provider 广播编排与 provider 业务字段适配。
- 业务层：写消息事实、写 Outbox、统一 dispatch 编排。
- Provider 层：入站/出站适配实现与 `target_key` 语义管理（“如何收/如何发”）。

### D2. Outbox（新增）

新增 `message_dispatch_outbox`（任务表，不替代 `message_deliveries`）：

- Outbox 职责：记录“待派发意图”，支持重试与恢复。
- Deliveries 职责：记录“每 endpoint 的投递结果”。
- 两者禁止合并为同一职责表。

### D3. 入站/出站统一语义

- 时间线消息（TEXT / CHAT_INFO）：统一“落 `message_history` + 写 outbox”。
- Typing 事件：不入 outbox，不写 deliveries，保持实时 best-effort。

### D4. 事务与 ACK 顺序（硬约束）

1. 写 `message_history`
2. 写 `message_dispatch_outbox`
3. 同事务提交
4. 之后才允许 WS 帧级 ACK
5. 异步 worker 读取 outbox 执行 dispatch，写 `message_deliveries`

禁止“先发 provider 再落库”或“事务内直接广播”。

### D5. target_key 归属

- `target_key` 是 provider 可投递目标标识。
- WebSocket（DEVICE 粒度）: `target_key = device_id`
- LeanCloud（USER 粒度）: `target_key = client_id`（即 `qiao_id`）
- 业务层只透传 endpoint 信息，不理解 provider 私有格式。

### D5.1 endpoint 粒度（新增约束）

- endpoint 是“可投递单元”，支持两种 scope：
  - USER（用户级）：适用于 LeanCloud 等第三方 provider 的原生用户路由
  - DEVICE（设备级）：适用于 WebSocket 等需要设备级在线状态与路由的 provider
- 不允许把所有 provider 强制收敛为 USER 或 DEVICE 单一粒度。
- `device_id` 与 `target_key` 不合并：
  - `device_id` 用于设备身份/离线游标语义
  - `target_key` 用于 provider 投递地址语义

### D6. 工厂重构方向

- 保留 `create_message_provider`（初始化、健康检查场景）。
- 新增“按 `MessageTransportProvider` 解析 sender”的工厂能力（dispatch 使用）。
- 下线核心发送路径对 `DEFAULT_MESSAGE_PROVIDER` 的依赖。

### D7. WebSocket 位置

- 拆分为两层：
  - Provider 语义层：`services/message/providers/websocket/*`（endpoint sender + 入站 payload 适配）
  - Transport 运行时层：`services/message/websocket/*`（连接管理、状态维护、发送队列）
- WebSocket 握手与协议接入仍在 API 层（`api/ws/messages.py`）；入站业务字段解析与 `InboundMessageEvent` 转换在 provider 层实现。

### D8. LeanCloud 改造范围

LeanCloud Provider 需要改造但不重写：

- 保留初始化、健康检查、webhook 解析。
- 补齐基于 `target_key=client_id/qiao_id`（USER 粒度）的 endpoint 投递能力。
- 与 WS sender 对齐统一 dispatch 契约。

---

## 设计约束

1) 不做向后兼容兜底（不允许静默 fallback）。
2) 不新增“平台层/中台层”等厚抽象。
3) dispatch 只能有一个业务编排入口。
4) 所有 provider 投递结果统一落 `message_deliveries`。
5) Outbox 失败可重试，消息事实不可回滚覆盖。
6) 不强制所有 provider 统一为同一 endpoint 粒度（USER/DEVICE 可并存）。

---

## 数据模型调整

### 新增表：message_dispatch_outbox

建议字段（最终以 data-dict/SQL 为准）：

- `id`（Snowflake）
- `outbox_type`（本任务至少支持 `timeline_fanout`）
- `msg_id_server`
- `owner_user_id`
- `status`（pending / processing / done / failed）
- `attempt_count`
- `next_retry_at`
- `locked_at`
- `last_error_code`
- `last_error_detail`
- `created_at`
- `updated_at`

约束建议：

- `UNIQUE (outbox_type, msg_id_server)`（防重复出队）
- `INDEX (status, next_retry_at)`（worker 扫描）

---

### 调整表：message_endpoints（本任务同步调整）

新增字段建议：

- `endpoint_scope`（USER / DEVICE）

字段语义与约束建议：

- `device_id`：
  - DEVICE scope 必填
  - USER scope 允许为空
- 保留 `target_key`（provider 投递地址），不与 `device_id` 合并
- 约束建议：
  - `CHECK`：USER scope 必须 `device_id IS NULL`
  - `CHECK`：DEVICE scope 必须 `device_id IS NOT NULL`
  - USER scope 唯一：`UNIQUE (provider, user_id, target_key)`
  - DEVICE scope 唯一：`UNIQUE (provider, user_id, device_id)`

## 计划改造点（代码层）

1) `backend/app/services/message/providers/base.py`
   - 增加 endpoint 发送协议（如 `send_to_endpoint`）。

2) `backend/app/services/message/providers/factory.py`
   - 增加按 `MessageTransportProvider` 解析 sender 的能力。
   - 下线默认 provider 发送核心路径。

3) `backend/app/services/message/inbound/router.py`
   - 入站统一写 `message_history + outbox`（同事务）。

4) `backend/app/services/message/outbound/sender.py`
   - 出站统一写 `message_history + outbox`（同事务）。
   - 移除直接 provider 发送与分散 delivery 写入。

5) `backend/app/services/message/dispatch/*`（轻量新增模块）
   - outbox enqueue/dequeue
   - dispatch 编排（查 endpoint -> 按 provider 分发 -> 记录 deliveries）

6) `backend/app/models/message/routing.py` + `backend/database/init/*.sql` + Alembic
   - `message_endpoints` 增加 `endpoint_scope` 并调整约束（USER/DEVICE 双粒度）。

7) `backend/app/services/message/providers/leancloud/*`
   - 补齐 endpoint 投递适配（`target_key=client_id/qiao_id`，USER 粒度）。

8) `backend/app/services/message/providers/websocket/*`
   - 新增 WebSocket provider sender 适配（DEVICE 粒度，供 dispatch 工厂按 provider 解析）。
   - 新增 WebSocket 入站适配（WS payload -> `InboundMessageEvent`）。

9) `backend/app/services/message/websocket/*`
   - 保持 transport 运行时实现（连接管理/状态/发送队列），不承载 provider 工厂语义。

10) `backend/app/api/ws/messages.py`
   - 移除 API 层 provider 广播编排。
   - 保留协议处理与 ACK（ACK 仅在“消息事实 + outbox 提交成功”后返回）。
   - API 层仅负责帧级协议处理；业务入站字段转换委托 provider 适配层。

11) `backend/app/services/message/processing/sender.py`
   - 移除手工 WS 广播调用，统一走 outbox。

12) `backend/app/main.py`
    - 启停 outbox worker（与现有 scanner 生命周期一致）。

---

## 文档与数据库同步范围（实施时）

- `docs/spec/message/websocket.md`
- `docs/spec/message/schema.md`
- `docs/spec/message/failure-handling.md`
- `docs/spec/message/leancloud.md`
- `docs/api/websocket-messages.md`（若对外行为变化）
- `docs/data-dict/message.md`（新增 outbox + 调整 endpoints scope）
- `backend/database/init/*.sql`（新增表/索引）
- Alembic migration（与 init 脚本一致）

---

## 验收标准

1) WS / LeanCloud 入站都通过统一“落库 + outbox”路径，不在 API 层广播。
2) 出站同样通过 outbox 派发，不再直接按默认 provider 发送。
3) dispatch 按 endpoint.provider 分发；`message_deliveries` 统一写入且语义一致。
4) 进程在“消息提交后、派发前”崩溃时，重启后 outbox 能补派发。
5) typing 不入 outbox、不写 deliveries，时间线消息入 outbox。
6) `target_key` 语义由 provider 内部管理，业务层不耦合 provider 细节。
7) `/validate` 全部通过后才可报告完成。

---

## 风险与注意事项

1) LeanCloud 现有发送目标是 `client_id`（当前系统等同 `qiao_id`），切到 endpoint 发送需严格校验 target_key 与 provider API 一致。
2) WebSocket 多实例广播仍依赖 Hub（如 Redis PubSub）；本任务不改变该扩容前提。
3) 需防止重复投递与重复落库，严格依赖唯一约束与幂等键。
4) outbox worker 需具备并发锁与超时恢复，避免卡死与重复消费。

---

## 2026-02-21 评审拍板补充

1) LeanCloud endpoint 生命周期采用 **1B**：
   - 采用独立 Presence 注册/续租流程维护 `message_endpoints`（USER scope）。
   - `lc-im/signature` 仅负责 SDK 登录签名，不承担 endpoint 注册语义。

2) 权限拒收链路采用 **2B**：
   - 业务拒收不再以异常驱动流程。
   - 统一返回业务拒绝结果（`business_rejected`），并在该路径写入 CHAT_INFO（timeline + outbox）。

3) Provider 出站回执归档采用 **3B**：
   - 移除 `message_history.msg_id_provider_outbound` 语义与文档口径。
   - Provider 回执统一落 `message_deliveries.provider_msg_id`。

4) Outbox 重试口径采用 **4B**：
   - 首次派发后，最多再重试 3 次（1m / 5m / 15m）。
   - `attempt_count` 仅统计重试次数，不包含首次派发。

---

## 当前结论状态

- 方案已确认：**Provider 工厂重构 + 统一业务 dispatch + Provider 管理 `target_key` + Outbox 派发**。
- 当前阶段为方案文档，等待进入实施阶段。
