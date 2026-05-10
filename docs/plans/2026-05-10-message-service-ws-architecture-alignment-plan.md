# 2026-05-10 消息服务 WS 架构收敛实施计划

## 文档状态

- 状态：已实施
- 创建日期：`2026-05-10`
- 更新日期：`2026-05-10`
- 本文用途：记录消息服务后续改动任务的实施输入与验收口径

## 背景状态

- 用户消息传输运行通道采用 WebSocket。
- 消息核心表结构保留多 provider 通用定义。
- 审查结论包含三类收敛任务：分发运行策略收敛、provider 扩展机制收敛、前端消息适配字段语义收敛。

## 目标

1. 运行态保持 WebSocket 单通道，避免分发任务进入无效重试。
2. provider 抽象层保留可扩展结构，后续新增 provider 通过注册完成接入。
3. 前端消息适配字段使用中性语义命名，降低后续 provider 接入成本。

## 范围

### 纳入范围

- 后端消息分发任务 `_dispatch_timeline_task` 的 endpoint 选择与失败处理策略。
- `backend/app/services/message/providers/*` 的 provider 注册与 sender/lifecycle 查询机制。
- 小程序消息适配层字段命名与会话参数命名收敛（adapter types、service、adapter）。
- 对应文档同步（`docs/spec/message/*`、`frontend/mp-weixin/AGENTS.md`、相关接口文档）。

### 不纳入范围

- 邀请码/权益并发一致性改造。
- 消息核心表结构约束收紧（保持多 provider 通用定义）。

## 实施内容

### 1. 分发运行策略收敛

- `message_dispatch_outbox` 任务分发仅选择 `provider = WEBSOCKET` 的活跃 endpoint。
- 非 WebSocket endpoint 不参与本轮投递与重试判定。
- `failed_count` 仅统计真实发送失败，不统计未纳入运行通道的 endpoint。
- 保持 outbox 任务状态语义：成功完成写 `DONE`，真实失败进入重试与告警。

### 2. Provider 扩展机制收敛

- 引入 provider registry：统一管理 sender 与 lifecycle provider 的注册与查询。
- WebSocket sender 通过 registry 注册。
- lifecycle provider 在 registry 中保留扩展点，当前运行态仅注册有效实现。
- 分发侧按 endpoint provider 查询 sender；未注册 provider 记录结构化错误并隔离处理，不影响已注册 provider 的成功投递。

### 3. 前端字段语义收敛

- `lc_msg_id`、`lc_timestamp` 改为中性 provider 字段命名。
- `im_conv_id` 改为通用会话提示字段命名。
- `app_id`、`app_key`、`signature` 相关字段命名按 WS 鉴权语义重命名。
- `message/service.ts`、`adapter-types.ts`、`websocket.ts`、`conversation-store.ts` 与 schema 校验保持同一命名口径。

### 4. 文档与契约同步

- 同步更新消息域 spec/api 文档中的字段命名与运行通道描述。
- 文档内容仅描述实施后有效状态。

## 验收标准

1. 同一 outbox 任务在存在 WebSocket 可用 endpoint 时，投递成功不会被非运行通道 endpoint 拉入失败重试。
2. provider 接入点通过 registry 管理，新增 provider 仅需注册实现与枚举映射。
3. 小程序消息适配层不出现 LeanCloud 专属字段命名。
4. `docs/spec/message/*` 与实际实现字段命名一致。

## 实施后验证

- 后端：分发任务单测/集成验证覆盖“WS 成功 + 非运行通道 endpoint 共存”场景。
- 前端：`npm run type-check` 与消息发送/接收链路验证通过。
- 数据库：不调整消息核心表结构；新增迁移 `backend/alembic/versions/20260510_01_remove_leancloud_message_runtime_configs.py` 清理 LeanCloud 消息运行配置项。

## 实施结果

1. 后端分发任务只对 `provider=WEBSOCKET` endpoint 执行时间线投递，非运行通道 endpoint 不再触发失败重试计数。
2. provider 工厂改为 registry 机制，sender/timeline/lifecycle 查询统一通过注册表完成。
3. 小程序消息适配层字段改为 provider 中性语义命名，移除 LeanCloud 专属字段口径。
4. 数据迁移已落地：`20260510_01_remove_leancloud_message_runtime_configs.py` 删除 `leancloud_im_server_url`、`leancloud_im_service_conversation_id`、`leancloud_im_webhook_token`，并提供 downgrade 恢复逻辑。
