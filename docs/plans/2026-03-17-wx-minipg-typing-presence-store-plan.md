# 2026-03-17 小程序 Typing 状态全局持久化方案

## 问题点

- 小程序 Chat 页的 typing 展示依赖 `frontend/mp-weixin/utils/message/message-state-store.ts` 的 `isTyping`，该状态只维护“当前会话”。
- Chat 页 `onUnload` 会调用 `messageStateStore.clearConversation()`，导致 typing 状态随页面退出被清空。
- typing 事件在 `messageStateStore` 内按 `state.convId` 过滤，非当前会话的 typing 事件不会更新状态，页面再次进入时无法恢复“当前真实状态”。

## 需求点

- typing 状态不受页面切换影响；在应用进程内持续维护。
- 多个会话的 typing 状态互不干扰，按 `conv_id` 独立维护。
- typing 的展示与消失规则保持不变，遵循 `docs/spec/message/typing.md`：
  - 只展示对方 typing
  - 收到对方 `typing_end` 立即隐藏
  - 收到对方 TEXT 立即隐藏
  - 本端发送消息立即隐藏
  - 兜底超时 30 秒自动隐藏
- 小程序从后台回到前台、IM 断线/重连等场景：
  - 若期间收到非 typing 消息，则清除该会话 typing 状态
  - 若期间未收到非 typing 消息，则 typing 状态按超时自然过期
- typing 乱序判断使用本地 `received_time`。
- 退出登录/切换账号必须清空全部 presence 状态。
- 会话列表暂不展示 typing 状态。
  - 非 typing 消息定义：
    - 会话内对方发送的业务消息（非 typing 类）属于“非 typing 消息”，会触发清除 typing
    - `MESSAGE_TYPE.NOTIFICATION` 不属于对话消息，不触发清除 typing
    - `MESSAGE_TYPE.CHAT_INFO` 不属于对方发送消息，不触发清除 typing

## 方案定义

### 全局 Presence Store

新增全局 `ConversationPresenceStore`（单例），作为 typing 的唯一事实来源：

- 位置：`frontend/mp-weixin/utils/message/conversation-presence-store.ts`
- Key：`convId`
- Value（每会话记录）：
  - `isTyping: boolean`
  - `expiresAtMs: number | null`（`now + typingTimeout`）
  - `timer: ReturnType<typeof setTimeout> | null`（每会话一个计时器）
  - `lastTypingReceivedAtMs: number`（本地 `received_time`）
  - `lastNonTypingActivityAtMs: number`（本地接收对方“非 typing 业务消息”或本端发送消息的时间）
  - `currentUserId: string`（从本地用户信息读取，用于只展示对方 typing 的过滤）

对外能力（页面层使用）：

- `getTyping(convId): boolean`
- `subscribeTyping(convId, cb): () => void`（仅对该会话变化通知）
- `clearAll()`（登出/切号时调用）
- `clearTyping(convId)`（本端发送消息/清空会话时调用）

### 事件接入（与页面生命周期解耦）

`ConversationPresenceStore` 直接订阅 `frontend/mp-weixin/utils/message/event-bus.ts`：

- `onTyping(payload)`：
  - 先进行身份过滤（只展示对方 typing）：
    - `payload.to_qiao_id === currentUserId`
    - `payload.from_qiao_id !== currentUserId`
    - 任一不满足则忽略该事件
  - 乱序过滤使用本地 `received_time`，且 typing_start/typing_end 均参与判断：
    - 设 `dropBeforeMs = max(lastNonTypingActivityAtMs, lastTypingReceivedAtMs)`（忽略空值按 0 处理）
    - 若 `payload.received_time < dropBeforeMs`，丢弃该事件
  - `payload.typing=true`：
    - `isTyping=true`
    - `lastTypingReceivedAtMs=payload.received_time`
    - 刷新 `expiresAtMs=now+typingTimeout`
    - 取消旧 `timer` 并设置新 `timer`，到期后执行 `isTyping=false` 并通知订阅者
  - `payload.typing=false`：
    - `lastTypingReceivedAtMs=payload.received_time`
    - `isTyping=false`，清空 `expiresAtMs`
    - 取消 `timer`
- `onMessage(storedMessage)`（对话内、对方发送的非 typing 业务消息）：
  - 先按 `conv_id` 获取该会话记录（无则初始化）
  - 过滤规则：
    - `storedMessage.message_type` 为 `MESSAGE_TYPE.TYPING_START|MESSAGE_TYPE.TYPING_END`：忽略（不作为“非 typing”）
    - `storedMessage.message_type === MESSAGE_TYPE.NOTIFICATION`：忽略（不属于对话消息）
    - `storedMessage.message_type === MESSAGE_TYPE.CHAT_INFO`：忽略（不属于对方发送消息）
    - 身份过滤（只处理对方发来的消息）：
      - `storedMessage.to_qiao_id === currentUserId`
      - `storedMessage.from_qiao_id !== currentUserId`
      - 任一不满足则忽略
  - 满足过滤后：
    - 更新 `lastNonTypingActivityAtMs=now`
    - `isTyping=false`，清空 `expiresAtMs`
    - 取消 `timer`

超时逻辑：

- typing 的“过期判断”基于 `expiresAtMs` 与 `Date.now()`，不依赖页面是否在前台。
- 过期清理由每会话 `timer` 触发，并在 `getTyping/subscribeTyping` 中做一次“过期自检与清理”，用于兜底定时器延迟（前后台切换等）。

### 本端行为清理规则

- `clearTyping(convId)`：
  - 更新 `lastNonTypingActivityAtMs=now`
  - `isTyping=false`，清空 `expiresAtMs`
  - 取消 `timer`

### Chat 页接入

Chat 页不再依赖 `messageStateStore.isTyping`：

- 保留 `data.isContactTyping` 作为 UI 状态字段（用于 navbar slot）。
- 在 `onLoad` 获取 `convId` 后：
  - 订阅 `ConversationPresenceStore.subscribeTyping(convId, ...)`，将变化同步到 `isContactTyping`
  - 进入页面时读取一次 `getTyping(convId)` 初始化 `isContactTyping`
- 在 `onUnload` 仅取消订阅，不清除 presence。
- 本端发送消息时调用 `ConversationPresenceStore.clearTyping(convId)`，实现“本端发送消息立即隐藏 typing”。

### MessageStateStore 调整

`frontend/mp-weixin/utils/message/message-state-store.ts` 仅负责消息列表状态：

- 移除 `isTyping` 字段与 typing 计时器。
- 移除对 `messageEventBus.onTyping` 的订阅与处理。
- `MessageStoreState` 中移除 `isTyping`，Chat 页改为分别订阅：
  - 消息：`MessageStateStore.subscribe(...)`
  - typing：`ConversationPresenceStore.subscribeTyping(...)`

### 登出/切号清理

在会话清理唯一入口调用 `ConversationPresenceStore.clearAll()`，清空全部会话 presence：

- 位置：`frontend/mp-weixin/utils/auth-service.ts` 的 `private _clearStoredSession()`

### 初始化时机

`ConversationPresenceStore` 必须在进入 Chat 页之前完成 `messageEventBus` 订阅，保证页面未打开时也能维护状态：

- 在 `frontend/mp-weixin/utils/message/service.ts` 初始化链路中引入 `ConversationPresenceStore`，确保消息服务启动后 presence 即开始跟踪。

### 清空会话场景

清空聊天记录/删除联系人后必须清除该会话 typing 状态：

- 调用：`ConversationPresenceStore.clearTyping(convId)`

## 实施步骤

1. 新增 `conversation-presence-store.ts`，接入 `messageEventBus.onTyping` 与 `messageEventBus.onMessage`。
2. 重构 `message-state-store.ts`：移除 typing 字段、订阅与计时器相关逻辑。
3. 修改 `pages/chat/chat.ts`：改为订阅 `ConversationPresenceStore` 驱动 `isContactTyping`；发送消息时调用 `clearTyping`；`onUnload` 不再影响 typing。
4. 修改会话清理逻辑：在 `auth-service._clearStoredSession()` 调用 `clearAll()`。
5. 修改清空会话相关页面：清空聊天记录/删除联系人后调用 `clearTyping(convId)`。
6. 运行 `frontend/mp-weixin` 下 `npm run check`，并进行手工验收场景验证。

## 验收标准

- 退出 Chat 页再进入同一会话：typing 状态不因页面切换被清空，按事件与超时规则收敛。
- 切换到会话 B 期间，会话 A 的 typing 状态仍会被 typing_end / 对方 TEXT / 本端发送 / 超时规则正确更新。
- 同时存在多个会话 typing：状态互不干扰，按各自 `conv_id` 独立超时与清除。
- 退出登录/切换账号后：所有 typing 状态清空。
- 会话列表无 typing 展示变更。

## 实施结果

- 未实施
