# 管理后台 Persona 批量创建页实施计划（队列化提交与分流重试）

## 问题点

1. 现有 `ai_personas` 在管理端仅支持单条创建，批量运营效率低。
2. Persona 创建与 profile 昵称/头像补录缺少统一批处理流程，失败修复成本高。
3. 头像上传虽有成熟链路，但未与 persona 批量创建流程打通。
4. 批量操作缺少条目级状态与重试分流，无法稳定完成“大队列全量尝试”。

## 需求点

1. 提供独立的管理端自定义页面，按 `AI Type` 一次性生成多条 persona 草稿条目。
2. 每条条目支持编辑 `nickname` 与头像；其余 persona 字段使用默认值或空值。
3. 每条条目头像区域支持文件选择、拖拽、剪贴板粘贴。
4. 支持条目级提交/重试与队列级提交，队列执行过程中逐条提交并展示状态。
5. 队列执行必须“全量尝试”：单条失败不阻断后续条目。
6. 页面保留成功条目，等待用户手动清理。

## 已拍板交互决策（固定）

1. 成功条目不会在提交后自动清除。
2. 支持单条条目提交或重试。
3. 当存在失败条目时，页面提供三种队列按钮：
   - `提交新增内容`（仅处理新增条目）
   - `重试失败内容`（仅处理失败条目）
   - `提交所有`（处理新增与失败条目）
4. 支持条目手动删除。
5. 支持一键移除已成功条目。

## 术语与状态定义

### 条目状态

- `draft`：新增未提交。
- `submitting`：提交中。
- `success`：提交成功。
- `failed`：提交失败。

### 条目持久字段（前端队列模型）

- `local_row_id`：前端本地唯一 ID。
- `type_id`：目标 AI Type。
- `nickname`：目标 profile 昵称。
- `avatar_input`：头像输入（文件对象或空）。
- `persona_id`：已创建 persona 的 ID（成功创建后回填）。
- `profile_id`：已创建/关联 profile 的 ID（成功创建后回填）。
- `failed_step`：失败步骤标识。
- `last_error`：最近一次错误信息。

## 提交行为规范

### 队列按钮语义

1. `提交新增内容`：仅提交 `draft`。
2. `重试失败内容`：仅提交 `failed`。
3. `提交所有`：提交 `draft + failed`。

### 单条按钮语义

1. 对 `draft` 条目显示 `提交`。
2. 对 `failed` 条目显示 `重试`。
3. 单条执行不影响其他条目状态。

### 执行策略

1. 队列执行采用逐条串行。
2. 单条失败后记录错误并继续下一个条目。
3. 队列完成后输出统计：尝试数、成功数、失败数。

## 防重复创建约束（强制）

1. 条目首次创建 persona 成功后，必须回填 `persona_id` 与 `profile_id`。
2. 后续重试同条目时，若存在 `persona_id/profile_id`，禁止再次创建 persona。
3. 有 `persona_id/profile_id` 的条目仅允许执行资料更新（昵称、头像）。
4. 通过该约束保证“创建成功但头像失败”场景不产生重复 persona。

## 后端实施方案

### 1) 新增批处理 API（管理端）

新增统一端点：`POST /admin-api/ai/persona-batch/submit-row`。

请求语义：

- 创建模式：未携带 `persona_id`。
- 重试/更新模式：携带 `persona_id`（可选携带 `profile_id`）。

服务端处理顺序：

1. 校验 `type_id` 有效。
2. 创建模式：创建 `ai_personas`，并确保 `profiles(owner_type=2)` 可用。
3. 更新 profile 昵称。
4. 处理头像上传并绑定 profile。
5. 返回条目结果与资源 ID。

响应字段：

- `status`: `success | failed`
- `persona_id`
- `profile_id`
- `failed_step`: `create_persona | ensure_profile | update_nickname | upload_avatar`
- `error_message`

### 2) 复用既有头像链路

1. 头像写入复用现有 profile 管理端上传能力与标准化策略。
2. 保持头像产物、审计日志、去重口径与现有 `profile avatar advanced edit` 一致。

### 3) 事务边界

1. 单条条目为单事务单位。
2. 单条失败只回滚该条，不影响队列其他条目。

## 前端实施方案

### 1) 新增自定义页面

- 新增页面：`Persona Batch Create`。
- 挂载到管理端 `AI Configuration` 分组。

### 2) 页面区块

1. 顶部操作区：选择 `AI Type`、输入批量数量、生成草稿条目。
2. 队列操作区：
   - `提交新增内容`
   - `重试失败内容`
   - `提交所有`
   - `一键移除已成功条目`
3. 条目列表区：每条展示昵称输入、头像拖拽区、状态、错误信息、单条按钮、删除按钮。

### 3) 头像交互

1. 每条条目独立拖拽区。
2. 支持三种输入：文件选择、拖拽、剪贴板粘贴。
3. 头像预览与替换在条目内完成。

## 按钮可用性规则

1. `提交新增内容`：存在 `draft` 条目时可用。
2. `重试失败内容`：存在 `failed` 条目时可用。
3. `提交所有`：存在 `draft` 或 `failed` 条目时可用。
4. 队列执行中禁用队列级按钮；单条执行中禁用该条操作按钮。

## 文档与代码范围

- 方案文档：
  - `docs/plans/2026-05-07-admin-persona-batch-create.md`
- 规范文档（实施时同步更新）：
  - `docs/spec/admin-panel/overview.md`
  - `docs/spec/ai/instance-lifecycle.md`
- API 文档（实施时同步更新）：
  - `docs/api/media.md`（若复用/扩展头像接口说明）
  - 新增管理端 persona 批处理 API 文档（`docs/api/admin-*.md`）
- 后端实现：
  - `backend/app/api/admin/`（新增 persona 批处理路由）
  - `backend/app/services/ai/`（新增批处理编排服务）
  - `backend/app/admin/views/`（新增自定义页面 view）
  - `backend/app/admin/templates/custom_views/`（新增页面模板）
  - `backend/app/admin/static/js/`（新增页面脚本）
- 测试：
  - 后端 API 与服务层测试
  - 前端关键交互与状态流转自测

## 验收标准

1. 可按指定 `AI Type` 一次性生成 N 条 persona 草稿条目。
2. 条目支持昵称编辑与头像三种输入方式（选择、拖拽、粘贴）。
3. 队列提交逐条执行，单条失败不阻断后续条目。
4. 三个队列按钮严格按定义分流目标条目。
5. 单条提交/重试可独立执行且结果正确落到条目状态。
6. 已创建成功条目重试时不会重复创建 persona。
7. 支持手动删除任意条目与一键移除已成功条目。
8. 队列执行结束后，页面可继续新增条目并再次提交。

## 状态

- 未开始
