# 管理后台：Pending Contact Requests 面板重构方案

## 文档目的

定义 `pending-contact-requests` 面板重构的实施范围、文档对齐范围、交付顺序与验收标准。

## 问题点

- 页面交互脚本未生效，详情/补模板/重试动作不可用。
- 重试接口路径与管理端路由前缀不一致。
- 列表与详情字段信息密度不足，缺少运营排障所需字段。
- `ai_type_id` 与 `failure_code` 仅展示原始值，缺少可读化信息。
- 时间字段未按操作员时区展示。
- 请求 ID 以 JSON Number 传输，存在大整数精度风险。

## 重构目标

- 建立稳定的管理端挂起请求工作台：可筛选、可定位、可诊断、可重试。
- 建立明确的数据契约：列表、详情、重试接口均使用管理端前缀与字符串 ID。
- 建立统一展示规则：失败原因可读化、AI 类型可读化、时间本地化并保留 UTC 原值。

## 范围

- 管理后台页面：`/qiao-dash/pending-contact-requests`
- 管理端 API：`/admin-api/contact-requests/*`
- 相关文档：
  - `docs/spec/contact/request-flow.md`
  - `docs/api/admin-contact-requests.md`（新增）
  - `docs/api/contact-requests.md`

## 固化决策

- 管理端接口统一使用 `/admin-api/*`。
- 页面采用 SSR 外壳 + 前端数据驱动渲染。
- 时间展示按浏览器时区格式化，同时保留 UTC 字段用于排障。
- 失败信息采用“失败代码 + 可读原因 + 操作建议”三段式。
- 补模板动作跳转 `ai_template` 列表并按 `type_id` 过滤。
- 重试动作本期交付单条重试；批量重试不在本期范围。
- 本期同步更新 spec 与 api 文档为当前目标契约。

## 信息架构（目标）

### 概览区

- Pending 总数
- 24h 重试成功数
- 24h 重试失败数
- Top AI 类型（`type_id + display_name + count`）
- Top 失败原因（`failure_code + reason_label + count`）

### 列表区

- 请求标识：`request_id`、`status`
- 参与方：`from_qiao_id`、`to_qiao_id`、`from_id`、`to_id`
- 请求上下文：`source`、`category_key`、`alias`、`tags`
- 失败诊断：`failure_code`、`failure_reason_label`、`failure_reason_hint`、`ai_type_id`、`ai_type_display_name`
- 生命周期：`created_at_local`、`updated_at_local`、`expires_at_local`、`last_retry_at_local`
- 重试状态：`retry_count`、`is_retryable`
- 操作：查看详情、补模板、立即重试

### 详情侧栏

- 基础信息分组：请求、参与方、上下文、生命周期
- 失败诊断分组：失败代码、可读原因、建议动作、模板相关信息
- 原始数据分组：`failure_detail` JSON（只读）

## 实施步骤

1. 新增管理端挂起列表/详情 API 契约并落文档。
2. 调整 spec 中管理端挂起面板行为定义与字段定义。
3. 调整前端页面交互契约：事件绑定、字段渲染、时区格式化、错误提示。
4. 调整后端视图/接口实现：路径前缀、字段聚合、AI 类型映射、失败原因映射、字符串 ID。
5. 完成验证：列表加载、详情展示、补模板跳转、单条重试、时间显示、筛选行为。

## 验收标准

- 页面进入后可正常加载概览与列表，控制台无 `ReferenceError`。
- 列表点击任意记录，详情侧栏展示完整字段分组内容。
- “补模板”跳转到 `ai_template` 列表并带 `type_id` 过滤参数。
- “立即重试”调用 `POST /admin-api/contact-requests/{request_id}/retry` 成功并反馈状态。
- 全部请求 ID 以字符串传输与渲染，无大整数精度丢失。
- 时间字段按浏览器时区显示，同时保留 UTC 原值用于排障。
- 文档与实现路径、字段、行为一致。

## 实施结果

- 状态：已实施（2026-05-22）
- 本文档已作为本次重构唯一方案文档。
