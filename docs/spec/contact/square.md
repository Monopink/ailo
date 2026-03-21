# Square 曝光逻辑

Square（发现页）用于展示可添加的 AI 联系人。

## 数据结构

### 分类表

- 表：`square_categories`
- 字段：`category_key`、`title`、`description`、`theme_key`、`icon_ref`、`sort_order`、`status`
- 约束：
  - `category_key` 唯一且不可修改
  - `theme_key` 取值集合由 `backend/app/enums/common.py` 的 `SquareCategoryTheme` 定义
  - `icon_ref` 格式为 `tdesign:<icon-name>`

### 上架表

- 表：`square_type_entries`
- 字段：`category_key`、`type_id`、`exposure_strategy`、`status`
- 约束：
  - `(category_key, type_id)` 唯一
  - `type_id` 在 ACTIVE 状态下唯一

## 分类曝光规则

- 分类接口仅返回 `square_categories.status=active` 的记录。
- 分类排序为 `sort_order ASC`，其次 `category_key ASC`。

## 列表查询规则

- Square 联系人列表按 `category_key` 维度查询与限流（接口定义见：`docs/api/discovery.md`）。
- 列表仅返回目标分类下 ACTIVE 的上架记录。
- 每条联系人卡片回传 `category_key` 用于来源回显。
- 分页与 `refresh_available_at` 的字段定义见：`docs/api/discovery.md`。

## Persona 选择与展示字段

- Square 展示对象为 `ai_personas`。
- 通过 `square_type_entries.type_id` 选取可用 persona。
- 展示字段来自 persona/profile：
  - `qiao_id`
  - `nickname`
  - `avatar_url`
  - `gender`
  - `tags`
  - `remark`
  - `bio`
  - `region`
  - `type_id`
  - `category_key`

## 预设联系人字段

- Square 列表回传 `tags` 与 `remark`，作为用户添加联系人时写入 `contacts.tags` 与 `contacts.remark` 的预设数据。
- 预设字段生成规则与联系人写入规则对齐，见：`docs/spec/contact/ai-creation.md` - tags 写入规则
- `square_categories.title` 作为预设 tags 的候选项时满足联系人标签校验规则，见：`docs/api/contacts.md` - 更新联系人信息 - `tags`

## 陌生人详情分类回显

- 陌生人详情接口支持可选 `category_key`（接口定义见：`docs/api/discovery.md`）。
- 返回 `category_key` 与 `category_title`。
- 未传入、无效或下线分类时，`category_key` 与 `category_title` 返回 `null`。
- 同时返回 `tags` 与 `remark`，规则见：`docs/spec/contact/ai-creation.md` - tags 写入规则
