# 联系人备注头像后端补全方案

## 已确认决策

- 用户文案统一使用“备注头像”。
- 系统内部命名统一使用 `custom_avatar`，不使用 `remark_avatar` 作为持久化字段命名。
- 复用现有联系人更新接口：`PUT /api/v1/contacts/{conversation_id}`。
- 复用现有媒资上传流程：前端先调用 `/api/v1/media/upload` 获取 `file_id`，再通过联系人更新接口提交 `avatar_file_id`。
- `avatar_file_id` 对应 `media_files.file_id`，不是数据库主键。
- 联系人备注头像持久化继续写入 `contacts.custom_avatar_key` 与 `contacts.custom_avatar_media_id`。
- 新增联系人头像展示模式字段 `avatar_display_mode`。
- `avatar_display_mode` 使用数字枚举：`1=original`，`2=custom`。
- `contacts.source` 同步改为数字枚举：`0=unknown`，`1=search`，`2=admin`，`3=system`，`4=recommend`，`5=discovery`，`6=contact_request`。
- 联系人列表与聊天列表只展示备注、备注头像；头像数据来源统一为联系人接口返回的 `avatar_url`。
- 联系人详情页同时展示备注头像与原始头像；数据来源为联系人接口返回的 `remark_avatar_url` 与 `original_avatar_url`。
- 首次设置备注头像时，如果此前不存在备注头像、且本次请求提交了 `avatar_file_id`、且请求未显式提交 `avatar_display_mode`，后端自动将 `avatar_display_mode` 设为 `2`。
- 后续再次更新备注头像但未显式提交 `avatar_display_mode` 时，保持当前展示模式不变。
- 清空备注头像时，后端强制将 `avatar_display_mode` 设为 `1`。

## 目标范围

- 补全联系人备注头像的后端写入、读取与展示模式决策链路。
- 补全联系人接口返回字段，使前端可同时获得当前展示头像、备注头像、原始头像。
- 保持现有用户头像上传链路与媒资表设计不变。

## 接口变更

### 1. 更新联系人信息

- 接口：`PUT /api/v1/contacts/{conversation_id}`。
- 在现有请求体基础上新增两个可选字段：
  - `avatar_file_id: string | null`
  - `avatar_display_mode: int`（可选，取值仅 `1` 或 `2`）

请求语义：

- `avatar_file_id` 传入非空字符串：设置或替换备注头像。
- `avatar_file_id` 显式传入 `null`：清空备注头像。
- `avatar_display_mode` 传入 `1`：展示原始头像。
- `avatar_display_mode` 传入 `2`：展示备注头像。
- `avatar_display_mode` 未传入：按既定自动规则处理，不触发模式覆盖。

服务端校验规则：

- `avatar_file_id` 必须对应已存在的 `media_files.file_id`。
- 该媒资必须属于当前用户。
- 该媒资必须是头像文件类型。
- 当 `avatar_display_mode=2` 且当前不存在备注头像，且本次也未提交有效 `avatar_file_id` 时，请求返回参数错误。

### 2. 联系人读取接口

- `GET /api/v1/contacts`。
- `GET /api/v1/contacts/{conversation_id}`。

返回字段调整：

- `avatar_url`：当前实际展示头像 URL。
- `remark_avatar_url`：备注头像 URL；未设置时为 `null`。
- `original_avatar_url`：原始头像 URL。
- `avatar_display_mode`：当前展示模式，取值 `1` 或 `2`。

字段语义：

- 列表页与聊天列表只使用 `avatar_url`。
- 联系人详情页同时使用 `remark_avatar_url` 与 `original_avatar_url`。
- `profile.avatar_url` 不再承载联系人展示头像决策。

## 数据模型变更

### 1. contacts 表

- 新增字段 `avatar_display_mode`。
- 字段类型：`INTEGER NOT NULL`。
- 默认值：`1`。
- 枚举语义：
  - `1=original`
  - `2=custom`

### 2. 既有字段复用

- `custom_avatar_key`：备注头像对象键。
- `custom_avatar_media_id`：备注头像媒资记录 ID。

不新增新的备注头像对象键或媒资列。

## 后端实现细节

### 1. Schema 层

- 扩展 `ContactUpdate`，新增：
  - `avatar_file_id: str | None`
  - `avatar_display_mode: int | None`（显式传入时不得为 `null`）
- 扩展联系人列表与详情响应 schema，新增：
  - `avatar_url`
  - `remark_avatar_url`
  - `original_avatar_url`
  - `avatar_display_mode`

### 2. API 层

- 在 `backend/app/api/v1/contacts.py` 中补充新字段校验。
- 保持文本字段长度校验逻辑不变。
- 头像展示模式非法值走参数错误。

### 3. Service 层

- 在 `backend/app/services/contact/service.py` 中补充：
  - 解析 `avatar_file_id` 到 `custom_avatar_key` 与 `custom_avatar_media_id`
  - 决策 `avatar_display_mode`
  - 生成 `remark_avatar_url`
  - 生成 `original_avatar_url`
  - 生成最终 `avatar_url`

展示头像决策顺序：

1. 计算 `original_avatar_url`。
2. 计算 `remark_avatar_url`。
3. 根据 `avatar_display_mode` 决定 `avatar_url`：
   - `1` 返回 `original_avatar_url`
   - `2` 返回 `remark_avatar_url`
4. 若模式为 `2` 但备注头像不存在，该状态视为非法状态，不向外暴露为静默回退。

首次设置备注头像自动切换逻辑：

- 更新前 `custom_avatar_key` 为空。
- 请求中提交了有效 `avatar_file_id`。
- 请求未显式提交 `avatar_display_mode`。
- 本次更新后将 `avatar_display_mode` 写为 `2`。

清空备注头像逻辑：

- 请求中 `avatar_file_id=null`。
- 本次更新同时清空 `custom_avatar_key`、`custom_avatar_media_id`。
- 本次更新强制将 `avatar_display_mode` 写为 `1`。

### 4. CRUD / Model 层

- `Contact` 模型补充 `avatar_display_mode` 字段定义。
- 初始化 SQL 与 Alembic 迁移同步新增该字段。

## 文档同步范围

- 更新 `docs/api/contacts.md`。
- 更新 `docs/data-dict/contact.md`。
- 如联系人展示规则已有规格文档引用头像字段，需同步更新对应文档。

## 验证清单

- 上传媒资后提交 `avatar_file_id`，联系人记录写入 `custom_avatar_key` 与 `custom_avatar_media_id`。
- 首次设置备注头像且未传 `avatar_display_mode` 时，返回结果中的 `avatar_display_mode=2`。
- 再次替换备注头像且未传 `avatar_display_mode` 时，返回结果保持原展示模式。
- 清空备注头像后，返回结果中的 `avatar_display_mode=1`。
- 当 `avatar_display_mode=1` 时，`avatar_url == original_avatar_url`。
- 当 `avatar_display_mode=2` 时，`avatar_url == remark_avatar_url`。
- 列表接口与详情接口返回的 `avatar_url` 决策一致。
- 参数非法、媒资不存在、媒资不属于当前用户、媒资类型错误时，返回符合错误码规范的错误响应。

## 实施顺序

1. 调整 schema、model 与迁移。
2. 调整联系人 service 的头像解析与展示决策。
3. 调整联系人列表与详情接口响应。
4. 同步 API 文档与数据字典。
5. 执行后端验证。
