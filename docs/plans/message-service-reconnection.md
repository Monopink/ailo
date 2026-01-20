# 消息服务断线重连方案（重写）

## 背景与现状
- 现象：运行一段时间后发送消息报 `MESSAGE_SERVICE_DISCONNECTED`
- 根因：断连后没有统一的连接生命周期管理；发送时仅检查 `connected`，无重连或状态恢复

## 设计原则
- **解耦**：Adapter 只负责传输细节，不承载连接策略
- **单一职责**：连接生命周期由 MessageService 统一管理
- **真实性**：不隐瞒失败，不做“假成功”
- **MVP 简化**：不引入不必要的心跳或复杂队列，先解决核心问题

## 目标与非目标
**目标**
- 前台可见状态下，连接中断后可自动恢复
- 发送前确保连接可用，保证消息状态系统语义不变
- 不破坏 LeanCloud 作为传输层的可替换性

**非目标**
- 不实现跨会话离线消息补发
- 不在 Adapter 内实现消息队列或业务策略
- 不引入未验证的 SDK 心跳机制

## 方案概述（架构层）

### 1) MessageService 负责连接生命周期
新增连接状态机与重连策略，向上提供 `resume/suspend/ensureConnected`：
- `resume()`：前台恢复连接策略
- `suspend()`：后台停止重连策略（不主动断开，避免频繁重连）
- `ensureConnected()`：发送前确保连接可用（单飞）
- `getConnectionState()`：供 UI 或错误提示使用

### 2) Adapter 仅上报连接事件
Adapter 扩展“连接状态回调”，只上报事件，不做策略：
- `onConnectionChange(handler)`
- 触发点：`connect()` 成功、SDK disconnect 事件

### 3) App 生命周期接入
`app.ts` 只通知生命周期：
- `onShow()` → `messageService.resume()`
- `onHide()` → `messageService.suspend()`

## 接口变更建议

### MessageAdapter（新增能力）
- 新增回调：
  - `onConnectionChange(handler: (state: ConnectionState) => void): void`
- `ConnectionState`：
  - `connected | connecting | disconnected | suspending`

### MessageService（新增能力）
- `resume(): Promise<void>`
- `suspend(): void`
- `ensureConnected(): Promise<void>`
- `getConnectionState(): ConnectionState`

## 连接状态机（简述）
- `disconnected` → `connecting`（重连开始）
- `connecting` → `connected`（成功）
- `connecting` → `disconnected`（失败，按策略退避）
- `connected` → `suspending`（进入后台）
- `suspending` → `connecting`（回到前台）

## 重连策略建议
- **前台**：指数退避 + 抖动（无硬上限）
  - 初始 1s，退避倍数 2，最大间隔 30s
  - 用户主动发送时立即触发一次连接尝试
- **后台**：停止重连，等待 `resume()`
- **签名**：每次重连都重新请求 `/lc-im/signature`，不复用旧签名

## 与消息状态系统的适配
- 发送流程保持不变：`SENDING → SENT / FAILED`
- `ensureConnected()` 仅作为发送前置条件，不改写状态语义
- 连接失败时仍写入 `FAILED` + `error_reason`
- Typing 消息同样走 `ensureConnected()`，避免状态分裂

## 需要改动的文件
- `frontend/wx-minipg/utils/message/adapter-types.ts`
- `frontend/wx-minipg/utils/message/leancloud.ts`
- `frontend/wx-minipg/utils/message/service.ts`
- `frontend/wx-minipg/app.ts`
- `frontend/wx-minipg/utils/message/ADAPTER_INTERFACE.md`

## 验证要点
1) 前台断网→恢复：自动重连，消息可继续发送
2) 后台停留→回前台：触发恢复连接
3) 连接失败：消息状态为 FAILED，错误原因清晰
4) 连续发送：无重复连接、无并发 connect

## 待确认事项
- LeanCloud SDK 的连接事件是否还需补充 `reconnect` 事件（若有）
- 是否需要在 UI 层展示“连接中/断开”状态（不影响架构，可选）

## 迁移说明
旧版方案已移至 `deleted/tasks/message-service-reconnection.md` 作为历史记录。该旧方案包含 Adapter 内重连策略与签名复用做法，不符合当前架构目标，不应继续沿用。
