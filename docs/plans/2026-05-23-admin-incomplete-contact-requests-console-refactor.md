# 管理后台：未完成请求面板与重试链路重构方案

## 文档目的

定义管理后台联系人请求处置面板与重试链路的重构目标、命名规范、接口契约、执行规则与验收标准。

## 问题点

- 面板命名与范围不一致：`pending-contact-requests` 仅表达 `PENDING`，与实际处置范围不匹配。
- 页面入口存在分叉，路径与资源命名不统一。
- 手动指定重试的阻断规则与执行语义未形成统一分级模型。
- 执行异常路径存在二次异常风险，导致首错被掩盖。

## 需求点

- 面板展示范围为“未完成请求”，不包含 `ACCEPTED` 与 `IGNORED`。
- 面板命名统一为“未完成请求”，入口路径统一。
- 手动指定重试支持以下告警可继续场景：
  - 模板状态非 `ACTIVE`
  - 模板 `type_id` 与请求目标类型不一致
- 手动指定重试对以下场景强阻断：
  - 该用户已使用过所选模板
- 执行重试前后语义一致：预检与执行共用同一规则分级。

## 重构范围

- 管理后台页面：`/qiao-dash/incomplete-contact-requests`
- 管理端 API：`/admin-api/contact-requests/incomplete/*` 与重试相关接口
- 联系人请求重试服务链路：`request_service`、`contact_handler`、`instance_creation`
- 管理后台前端静态资源与模板命名
- 文档：
  - `docs/spec/contact/request-flow.md`
  - `docs/api/admin-contact-requests.md`
  - `docs/api/contact-requests.md`（仅引用关系）

## 固化决策

- 面板中文名称：`未完成请求`。
- 面板范围：`PENDING`、`PROCESSING`、`FAILED`；不包含 `IGNORED` 与 `ACCEPTED`。
- 页面路径：`/qiao-dash/incomplete-contact-requests`。
- 管理端列表与概览路径：
  - `GET /admin-api/contact-requests/incomplete/overview`
  - `GET /admin-api/contact-requests/incomplete`
- 保留重试相关路径：
  - `GET /admin-api/contact-requests/ai-types/search`
  - `GET /admin-api/contact-requests/templates/search`
  - `POST /admin-api/contact-requests/{request_id}/retry-precheck`
  - `POST /admin-api/contact-requests/{request_id}/retry`
- 规则分级：
  - 阻断（BLOCKING）：不可执行，直接失败。
  - 告警（WARNING）：允许 `force_continue=true` 后执行。
- `TEMPLATE_ALREADY_USED_BY_USER` 归类为阻断。
- 阻断错误使用 `409 Conflict` 返回。
- 阻断尝试写入 `contact_request_retry_attempts`，结果状态为 `REJECTED`，并纳入统计。
- 重试模式字段 `mode` 使用字符串枚举 `ContactRequestRetryMode` 管理，仅允许 `AUTO`、`MANUAL`。
- `result_failure_code` 使用枚举管理；补充重试域枚举 `ContactRequestRetryFailureCode`，禁止重试错误魔法字符串。
- 增加业务拒绝可观测性：`REJECTED + AI_CONTACT_LIMIT_REACHED` 表示重试已执行，但因用户联系人上限未创建联系人。
- 禁止在重试链路使用魔法数字与魔法字符串；状态、结果、规则码、重试模式全部使用枚举或命名常量。
- 旧入口与旧命名不保留兼容层。

## 目标信息架构

### 概览区

- 未完成总数（`incomplete_total`）
- 24h 重试成功请求数（按 `request_id` 去重）
- 24h 重试失败请求数（按 `request_id` 去重）
- 24h 重试失败次数（按尝试事件计数）
- 24h 重试阻断次数（按尝试事件计数）

### 列表区

- 请求字段：`request_id`、`status`、`申请已过时长`
- 参与方字段：`from_qiao_id`、`to_qiao_id`、`from_id`、`to_id`
- 失败字段：`failure_code`、`failure_reason_label`、`failure_reason_hint`
- 类型字段：`ai_type_id`、`ai_type_display_name`
- 重试字段：`retry_count`、`last_retry_at`、`is_retryable`
- 时间字段：`created_at`、`updated_at`、`expires_at`（前端按浏览器时区展示）

## 重试规则模型

### 阻断规则（BLOCKING）

- 请求状态不允许重试
- 请求不存在
- 参数不合法
- 权限不足
- 指定模板不存在
- 指定 `AI Type` 不存在
- `TEMPLATE_ALREADY_USED_BY_USER`

### 告警规则（WARNING）

- `TEMPLATE_STATUS_NON_ACTIVE`
- `TEMPLATE_TYPE_MISMATCH`
- 其他允许执行但需确认的风险项

### 执行规则

- 预检返回 `blocking_errors`、`warnings`、`summary`。
- 执行前服务端再次按同一规则模型校验。
- 命中阻断规则直接返回 `409`，不进入实例创建链路。
- 仅命中告警规则时，要求 `force_continue=true` 才执行。

## 实施步骤

1. 重命名管理后台页面、视图、静态资源、模板与路由。
2. 重命名管理端列表与概览 API 路径与响应字段。
3. 重构重试策略为统一规则分级模型（阻断/告警）。
4. 重构重试执行链路事务边界与异常收敛，消除异常路径二次错误。
5. 更新统计口径与审计字段，纳入阻断尝试统计。
6. 对齐 `spec/api` 文档到新命名与新规则。

## 验收标准

- 面板入口为 `/qiao-dash/incomplete-contact-requests`，页面标题为“未完成请求”。
- 面板列表不展示 `IGNORED` 与 `ACCEPTED`。
- 重试预检可区分阻断与告警。
- 用户已使用模板场景在预检与执行均被阻断，返回 `409`。
- 模板非 `ACTIVE` 与类型不一致场景可告警后执行。
- 重试执行异常不再触发二次异常掩盖首错。
- 阻断尝试事件可查询、可统计。
- `docs/spec/*` 与 `docs/api/*` 与实现路径、字段、规则一致。

## 实施结果

- 状态：已实施（2026-05-23）
