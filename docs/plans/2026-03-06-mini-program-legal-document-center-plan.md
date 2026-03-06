# 小程序协议内容展示（MVP）实施方案

## 1. 目标与边界

- 当前阶段实现协议文档中心的数据管理与读取能力，客户端只负责展示。
- 微信隐私授权仅使用微信原生链路，系统不实现自定义隐私弹窗。
- 当前阶段不实现同意留痕、不实现协议门禁、不实现版本治理。
- 本方案覆盖客户端 `mini-program`，语言固定 `zh-CN`。

## 2. 固化决策

- 用户侧资源命名统一为 `legal-documents`。
- 协议文档通过 `doc_key` 定义，不预设固定协议类型。
- 首期默认文档键：`user_agreement`。
- `client_type` 仅由请求头 `X-Client` 推导，不接受 query/body 传入。
- 用户侧读取接口支持匿名访问，但必须携带 `X-Client`。
- `locale` 固定 `zh-CN`，MVP 不暴露 `locale` 入参。
- 内容双存储：`content_md`（真相源）+ `content_rendered`（展示内容）。
- `content_rendered` 由后端在保存时基于 `content_md` 生成，格式固定 `html`。
- 用户侧 API 仅下发展示字段，不返回 `content_md`。
- 批量读取时任一 `doc_key` 缺失即整体返回统一错误（all-or-nothing）。

## 3. 数据模型（极简）

### 3.1 legal_documents

- 用途：存储当前生效协议文档。
- 主键：`id`（Snowflake）。
- 字段：
  - `doc_key`：协议标识
  - `client_type`：客户端标识（当前 `mini-program`）
  - `locale`：语言（固定 `zh-CN`）
  - `title`：标题
  - `content_md`：编辑源
  - `content_rendered`：展示正文（HTML）
  - `status`：1=active，2=inactive
  - `created_at`，`updated_at`
- 唯一约束：`doc_key + client_type + locale`。

## 4. API 契约（api/v1）

### 4.1 GET /api/v1/legal-documents

- Header：`X-Client`（必填）。
- Query：`doc_keys`（逗号分隔，去重，按首次出现顺序处理）。
- 出参：
  - `items` 数组，元素字段为：
    - `doc_key`
    - `title`
    - `locale`（固定 `zh-CN`）
    - `content_rendered_format`（固定 `html`）
    - `content_rendered`
    - `updated_at`

### 4.2 GET /api/v1/legal-documents/{doc_key}

- Header：`X-Client`（必填）。
- 出参与列表元素字段一致。

### 4.3 错误约束

- 读取不到内容时返回统一用户侧错误，不做默认回退正文。
- 新接口错误响应遵循 `docs/api/error-codes.md`。

## 5. 管理端实现范围（Starlette Admin）

- 当前阶段使用 Starlette Admin ModelView 管理 `legal_documents`。
- 支持列表筛选（`doc_key/client_type/locale/status`）。
- 支持创建、编辑、启用、停用。
- 创建/编辑保存时同步渲染 `content_md -> content_rendered`。
- 管理端对 `legal_documents` 的写操作需写入 `admin_operation_logs`。
- 当前阶段不提供发布、归档、版本切换流程。

## 6. 小程序交互范围

- 登录页与关于页展示协议入口。
- 协议详情页通过 `legal-documents` API 拉取并渲染正文。
- 微信隐私政策入口固定调用 `wx.openPrivacyContract`。
- 登录按钮维持 `open-type="getPhoneNumber"`，隐私授权行为由微信原生能力处理。

## 7. 非目标（当前阶段明确不做）

- 不做协议同意状态查询接口。
- 不做同意提交接口。
- 不做后端协议门禁。
- 不做版本号、哈希校验、生效时间调度。

## 8. 演进约束

- `doc_key` 作为长期稳定标识，后续治理能力基于该标识扩展。
- `client_type` 与 `locale` 维度保持延续。
- 治理能力通过新增资源与新接口扩展，不在现有流程中增加回退逻辑。

## 9. 文档与数据库同步清单

- 数据库：
  - `backend/app/models` 新增 `legal_documents` 模型
  - `backend/alembic/versions` 新增迁移
  - `backend/database/init/01_schema.sql` 同步表结构
  - `backend/database/init/03_sample_data.sql` 增加最小样例
- 后端管理端：
  - `backend/app/admin/views` 新增 `legal_documents` 对应 ModelView
- 文档：
  - `docs/api` 新增 `legal-documents` 接口文档
  - `docs/api/error-codes.md` 补充模块注册与错误码
  - `docs/data-dict` 新增 `legal_documents` 数据字典
  - `docs/spec/client/mini-program` 补充协议展示规则
  - `docs/spec/client/base/profile-and-settings.md` 补充协议入口定义

## 10. 验收标准

- 小程序可通过 `legal-documents` API 获取并渲染协议正文。
- 用户侧 API 返回字段为展示字段，不返回 `content_md`。
- 微信隐私政策仅走微信原生链路，系统不介入授权兜底。
- 协议内容可在管理端按 `doc_key/client_type/locale` 维护。
- 系统不包含同意留痕、门禁、版本治理实现。
