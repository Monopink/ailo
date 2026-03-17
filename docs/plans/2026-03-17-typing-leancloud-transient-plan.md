# Task: LeanCloud Typing（Transient）闭环补齐（2026-03-17）

## 背景

小程序测试消息收发时未展示“对方正在输入…”。后端日志出现：

- `event=typing_unsupported_provider`
- `logger=app.services.message.dispatch.realtime`

当前线上（或本地测试）小程序消息通道使用 LeanCloud（`provider=2`），Typing 事件未被下发到该通道。

## 目标与约束

### 目标

1. 所有消息通道（包括 LeanCloud 与 WebSocket）均支持 Typing。
2. Typing 为 realtime best-effort 事件：
   - 不写入 `message_history`
   - 不进入 `message_dispatch_outbox`
   - 不写入 `message_deliveries`
3. LeanCloud Typing 双向均使用 `transient=true`：
   - 客户端上报 Typing（小程序 → LeanCloud）为 transient
   - 服务端下发 Typing（服务端 → LeanCloud → 客户端）为 transient
   - 备注：这里的 transient 指“暂态消息（transient message）”，不是“聊天室/暂态对话（transient conversation）”

### 约束来源

- `docs/spec/message/typing.md`
- `docs/spec/message/schema.md`
- `docs/plans/completed/2026-02-21-message-provider-architecture-alignment.md`（D3）

## 现状梳理（端到端）

### 前端（小程序）

1. UI 展示依赖 `isContactTyping`：
   - `frontend/mp-weixin/pages/chat/chat.wxml`：显示“对方正在输入...”
2. Typing 状态来自消息状态仓库：
   - `frontend/mp-weixin/utils/message/message-state-store.ts`
3. LeanCloud 适配器已能识别 `message_type=2/3` 并触发 typing 回调：
   - `frontend/mp-weixin/utils/message/leancloud.ts`
4. 客户端 Typing 上报当前通过发送 `message_type=TYPING_START/TYPING_END` 的消息实现：
   - `frontend/mp-weixin/utils/typing-manager.ts`

### 后端

1. Typing 扇出入口为 `fanout_typing_event`：
   - `backend/app/services/message/dispatch/realtime.py`
2. 当前 `fanout_typing_event` 只支持 `provider=WEBSOCKET`：
   - 对 `provider=LEANCLOUD` 记录 `typing_unsupported_provider` 并跳过
3. AI “打字模拟”会触发 Typing best-effort 扇出：
   - `backend/app/services/message/processing/sender.py` → `fanout_realtime_typing_best_effort`

## 问题定义

### P1：后端未对 LeanCloud 执行 Typing 下发

- 触发条件满足，但对 `provider=LEANCLOUD` 直接跳过
- 现象：小程序收不到 typing 事件，`isContactTyping` 永远不会被置为 `true`

### P2：文档口径不一致

- `docs/spec/message/typing.md`：描述仅 WebSocket 下发 typing
- `docs/spec/message/schema.md`：LeanCloud TypedMessage 定义包含 `message_type=2/3`（Typing）
- 小程序实现：按 `message_type=2/3` 处理 typing

### P3：LeanCloud Typing 未落地 transient 语义

- Typing 为状态事件，需满足“不入历史、不离线补投”的 best-effort 语义
- LeanCloud 侧需使用 `transient=true`

## 方案（实现）

### S1：客户端上报 Typing（LeanCloud SDK）

- 在 LeanCloud adapter 发送 Typing 时传入 `{ transient: true }`
  - 触发范围：`message_type=TYPING_START/TYPING_END`
  - 文件：`frontend/mp-weixin/utils/message/leancloud.ts`

### S2：服务端下发 Typing（LeanCloud REST）

1. 扩展 LeanCloud REST 发送函数支持可选参数 `transient`：
   - 文件：`backend/app/services/message/providers/leancloud/client.py`
2. 扩展 LeanCloud 发送服务透传 `transient` 到 REST 客户端：
   - 文件：`backend/app/services/message/providers/leancloud/service.py`
3. 在 `fanout_typing_event` 补齐对 `provider=LEANCLOUD` 的扇出实现：
   - 目标端点：`message_endpoints` 中 lease 未过期的 LeanCloud endpoints（USER scope）
   - 投递地址：`endpoint.target_key`（client_id / qiao_id）
   - 出站消息结构：TypedMessage `_lcattrs`，`message_type=2/3`，`content=""`
   - 强制 `transient=true`
   - 文件：`backend/app/services/message/dispatch/realtime.py`

### S3：文档同步（统一口径）

1. `docs/spec/message/typing.md`
   - 明确各 provider 的 typing 下发形式
   - LeanCloud：使用 `message_type=2/3` 且 `transient=true`
2. `docs/spec/message/leancloud.md`
   - 补充 Typing transient 语义
3. `docs/spec/message/schema.md`
   - 保持消息类型枚举不变，仅补充 transient 语义说明（如需）

## 实施记录（已完成）

### 文档对齐

- `docs/spec/message/typing.md`：补齐 LeanCloud typing + `transient=true` 口径
- `docs/spec/message/schema.md`：补充 Typing（transient）说明
- `docs/spec/message/special-types.md`：补充 LeanCloud typing 传输规则
- `docs/spec/message/leancloud.md`：补充 Typing（transient）章节，并修正 REST 端点与请求体示例

### 前端（小程序）

- `frontend/mp-weixin/utils/message/leancloud.ts`：Typing 消息发送使用 `{ transient: true }`
- `frontend/mp-weixin/libs/im.min.js.d.ts`：补齐 `Conversation.send(message, { transient })` 的类型定义（与 LeanCloud 文档一致）

### 后端

- `backend/app/services/message/dispatch/realtime.py`：补齐 LeanCloud typing fanout（不再对 provider=LEANCLOUD 直接跳过）
- `backend/app/services/message/providers/leancloud/client.py`：REST 发送支持 `transient` 字段透传
- `backend/app/services/message/providers/leancloud/service.py`：透传 `transient` 到 REST 客户端
- `backend/app/services/message/providers/leancloud/webhook.py`：过滤 `msg_id_client` 非 `client_` 前缀的 webhook 入站，防止服务端自发消息（含 typing）回环进入入站管线

### 本地校验

- 后端：`ruff format/check`、`mypy`、`lint-imports`（在 `backend/` 目录运行）通过
- 小程序：`npm run check` 通过

## 验收标准

1. 小程序 A 输入时，小程序 B 在同一会话页展示“对方正在输入...”，并在：
   - 收到 `TYPING_END` 时立刻隐藏；或
   - 收到对方 TEXT 时立刻隐藏；或
   - 30 秒超时隐藏（客户端兜底）
2. 后端日志不再出现 “对 LeanCloud endpoint 直接跳过 typing” 的行为（`typing_unsupported_provider` 针对 provider=2 消失）。
3. Typing 消息不进入离线拉取（不作为历史消息存在）。
4. 时间线消息 outbox 派发链路不受影响。

## 验证步骤

1. 双端在线（同一账号多端或两账号互聊均可），进入同一会话页：
   - 一端开始输入（持续 > 1s，满足防抖）
   - 另一端观察 navbar 文案变化
2. 断网/切后台/切会话：
   - 观察 typing 自动收敛（对方 TEXT/超时）
3. 离线补偿校验：
   - 触发离线拉取接口后，消息列表不包含 `message_type=2/3`

## 风险与处理

1. LeanCloud webhook 是否会回调服务端处理服务端下发的 transient Typing：
   - 已处理：webhook 入口硬过滤 `msg_id_client` 必须以 `client_` 开头；服务端自发消息使用非 `client_` 前缀，从而避免回环进入入站管线。
