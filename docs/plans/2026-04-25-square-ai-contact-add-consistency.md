# Square 添加联系人一致性修复（AI 请求链路）

## 目标

- 修复用户在小程序 Square/陌生人页添加 AI 联系人后，`CHAT_INFO(CONTACT_ADDED)` 可能缺失的问题。
- 保证 AI 联系人请求在“创建联系人 + 写入时间线提示消息 + 入队分发”上的事务一致性。
- 保持 AI 请求失败可见性策略：失败仅管理员可见，用户端不接收失败通知。
- 保证首页（index）在跨页返回场景自动可见新联系人，不依赖手动下拉刷新。

## 已确认决策

- AI 联系人请求保持异步 Worker 处理模式。
- 联系人接受成功时，采用单事务一致写入：联系人关系、`CHAT_INFO` 时间线消息、分发 outbox。
- 小程序首页采用双触发刷新：
  - `onShow` 固定触发一次远端联系人刷新。
  - 收到 `CHAT_INFO(CONTACT_ADDED)` 时触发联系人刷新。
- UI 层不拦截重复提交（包含 `PROCESSING`）；后端负责幂等忽略并返回统一成功响应。
- 已添加成功的联系人不允许重新提交。
- 管理员重试接口仅允许“挂起且可恢复”请求（模板缺失类）。
- 系统错误维持 `contact_requests.status=FAILED`。
- 采用单一路径落地，不保留并行逻辑。

## 现状问题

- AI Worker 路径存在事务提交缺口：联系人提交成功后，`send_chat_info` 的消息持久化与 outbox 入队未在同一提交边界内稳定提交，导致提示消息可能丢失。
- 管理员重试接口在执行重试前先清空 `failure_*` 并提交，后续失败时会产生挂起标识丢失风险。
- 重复提交路径会把 `PROCESSING` 请求改回 `PENDING`，存在并发竞态。
- index 页跨页返回时不保证固定远端刷新，导致“联系人已创建但首页未及时可见”。

## 实施方案

### 1. 后端：AI 接受链路事务重构

- 在 AI 请求接受路径中，统一在单次事务内完成以下写入：
  - `contacts` 创建（或恢复后更新）。
  - `contact_requests` 状态迁移到 `ACCEPTED`。
  - `message_history` 写入 `CHAT_INFO(CONTACT_ADDED)`。
  - `message_dispatch_outbox` 入队时间线 fanout 任务。
- 提交成功后返回统一响应；提交失败按异常路径回滚并按规则落状态。
- 维持系统错误为 `FAILED`，不改为 `IGNORED`。

### 2. 后端：重复提交与并发状态处理

- 重复提交命中 `PENDING/PROCESSING` 时，不改写进行中请求状态，不新增请求记录。
- 后端直接返回 `{"message":"请求已发送"}`，由既有处理流程继续推进。
- 已存在有效联系人关系时保持拒绝重复添加。

### 3. 后端：管理员重试收敛

- 管理员重试前置校验：
  - `status=PENDING`
  - `failure_code` 属于可恢复集合（模板缺失类）
- 校验通过后再执行重试与状态迁移。
- 系统错误（`FAILED`）不进入可恢复重试入口。

### 4. 前端：首页自动可见

- index 页 `onShow` 固定触发一次远端联系人刷新。
- 保留收到 `CHAT_INFO` 时的联系人刷新逻辑，用于实时更新。
- 刷新失败走既有降级策略，不阻断页面可用性。

### 5. 文档同步

- 同步更新以下文档为当前有效状态：
  - `docs/spec/contact/request-flow.md`
  - `docs/spec/contact/notification.md`
  - `docs/spec/client/base/discovery.md`
  - `docs/api/contact-requests.md`

## 实施步骤

1. 重构 `backend/app/services/contact/request_service.py` 中 AI 接受路径事务边界与重复提交分支逻辑。
2. 调整 `backend/app/services/contact/request_worker.py` 的状态回写策略，消除 `PROCESSING -> PENDING` 回退风险。
3. 收敛管理员重试入口（服务层 + Admin API/视图校验）。
4. 调整 `frontend/mp-weixin/pages/index/index.ts` 的 `onShow` 刷新触发策略。
5. 执行后端与小程序校验流程并完成文档同步。

## 验收标准

- 用户从 Square/陌生人页添加 AI 联系人后，系统可稳定生成并下发 `CHAT_INFO(CONTACT_ADDED)`。
- 不需要手动下拉刷新，返回 index 后可自动看到新联系人。
- 重复提交在 `PENDING/PROCESSING` 不产生脏状态迁移，不新建重复请求，接口统一返回成功文案。
- 管理员重试仅可操作挂起可恢复单；系统错误单保持 `FAILED`，不进入该入口。
- AI 添加失败不向用户推送失败通知，失败信息仅在管理员侧可见。

## 涉及文件

- `backend/app/services/contact/request_service.py`
- `backend/app/services/contact/request_worker.py`
- `backend/app/api/admin/contact_requests.py`
- `backend/app/admin/views/user_views.py`
- `frontend/mp-weixin/pages/index/index.ts`
- `docs/spec/contact/request-flow.md`
- `docs/spec/contact/notification.md`
- `docs/spec/client/base/discovery.md`
- `docs/api/contact-requests.md`
