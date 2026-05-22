# 管理后台：Pending Contact Requests 指定模板重试方案

## 文档目的

定义 `pending-contact-requests` 页面新增“指定模板重试”能力的实施范围、接口契约、数据落库与验收标准。

## 范围

- 管理后台页面：`/qiao-dash/pending-contact-requests`
- 管理端 API：`/admin-api/contact-requests/*`
- 联系人请求重试服务链路：`request_service`、`contact_handler`、`instance_creation`
- 审计与统计：`admin_operation_logs`、`contact_request_retry_attempts`（新增）

## 固化决策

- 页面新增“指定模板重试”按钮，点击后弹出模板选择弹窗。
- 弹窗模板选择使用 `backend/app/admin/static/js/components/search-select.js`。
- 预检为即时参考结果，不设置有效期，不做确认前重检；管理员确认后直接进入重试流程，以重试结果为准。
- 指定模板重试允许以下风险场景强制继续：
  - 模板已被该用户历史使用
  - 模板 `type_id` 与请求目标 `ai_type` 不一致
  - 模板状态为 `INACTIVE` 或 `USED`
- 权限粒度：指定模板重试仅 `SUPER_ADMIN` 可执行。
- 统计采用双维度：
  - 需求侧：`requested_ai_type_id`
  - 供给侧：`selected_template_type_id`
- 新增重试事件表 `contact_request_retry_attempts`，每次重试尝试一行，支持“请求数”与“尝试次数”两种口径。

## 信息架构

### 列表动作

- 查看详情（弹窗）
- 补模板（跳转模板列表）
- 重试（自动选模板）
- 指定模板重试（弹窗选择模板并预检后确认执行）

### 指定模板重试弹窗

- 模板选择器（Search Select）
- 模板详情区：`id`、`display_name`、`type_id/type_name`、`status`、`is_reusable`、`priority`、`style_id`、`personality_id`、`timezone`、`updated_at`
- 预检结果区：
  - `checks[]`（逐项检查）
  - `warnings[]`（风险提示）
  - `summary`（风险总览）

## 接口设计

### 预检接口

- `POST /admin-api/contact-requests/{request_id}/retry-precheck`
- 输入：`selected_template_id`（可选；为空表示自动模板重试预检）
- 输出：
  - 请求快照
  - 目标类型信息（`requested_ai_type_id`）
  - 模板快照（如指定模板）
  - 检查结果（`checks`）
  - 风险提示（`warnings`）
  - 汇总信息（`summary`）

### 执行重试接口

- `POST /admin-api/contact-requests/{request_id}/retry`
- 输入字段：
  - `mode`: `AUTO` | `MANUAL`
  - `selected_ai_type_id`（`mode=MANUAL` 必填）
  - `selected_template_id`（`mode=MANUAL` 可选）
  - `force_continue`（布尔）
  - `idempotency_key`（必填）
  - `alias`、`tags`（可选）
- 行为：
  - 复用现有重试主链路创建联系人
  - 不可复用模板保持同一消耗语义（创建成功后标记消耗）
  - 记录管理员操作审计与重试尝试事件

## 数据模型

### 新增：contact_request_retry_attempts

- 一次重试尝试一行，包含：
  - 基础：`id`、`request_id`、`attempt_no`、`operator_admin_user_id`、`operator_username`
  - 输入：`mode`、`selected_template_id`、`force_continue`、`idempotency_key`
  - 预检：`precheck_checks`、`precheck_warnings`、`precheck_summary`
  - 类型归属：`requested_ai_type_id`、`selected_template_type_id`、`is_type_mismatch`
  - 输出：`result_status`、`result_failure_code`、`result_failure_detail`
  - 时间：`started_at`、`finished_at`、`created_at`

### admin_operation_logs

- 继续用于管理员操作审计。
- 通过 `operation_meta` 写入结构化字段：`request_id`、`mode`、`selected_template_id`、`force_continue`、`warnings_count`、`result_status`。

## 统计口径

- `24h 重试失败请求数`：按 `request_id` 去重统计。
- `24h 重试失败次数`：按 `contact_request_retry_attempts` 事件行统计。
- 类型统计默认展示需求侧（`requested_ai_type_id`），报表支持切换供给侧（`selected_template_type_id`）。

## 实施步骤

1. 更新管理端 API 契约文档。
2. 更新联系人请求流程规范文档（挂起处理、弹窗交互、预检与执行语义、统计口径）。
3. 新增重试事件表迁移与数据字典定义。
4. 实施后端预检接口、执行接口参数扩展、权限校验、审计与事件落库。
5. 实施前端指定模板弹窗、预检展示、确认执行、反馈刷新。
6. 联调验证：权限、异常提示、重试成功/失败、统计准确性。

## 验收标准

- 页面存在“指定模板重试”入口，`SUPER_ADMIN` 可用，非 `SUPER_ADMIN` 不可执行。
- 选择模板后可展示模板详情与预检结果，风险场景有重点提示。
- 管理员确认后可执行重试，执行结果以实时处理结果为准。
- 自动重试与指定模板重试共用同一联系人创建与模板消耗链路。
- 产生完整审计记录与重试事件记录。
- 面板可同时展示“24h 重试失败请求数”和“24h 重试失败次数”。

## 实施结果

- 状态：已实施（2026-05-22）
