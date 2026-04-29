# Square 曝光逻辑

Square（发现页）用于展示可添加的 AI 联系人。

## 数据结构

### 分类表

- 表：`square_categories`
- 字段：`category_key`、`title`、`description`、`theme_key`、`icon_ref`、`sort_order`、`status`、`minor_visible`、`review_visibility_scope`
- 约束：
  - `category_key` 唯一且不可修改
  - `theme_key` 取值集合由 `backend/app/enums/` 的 `SquareCategoryTheme` 定义
  - `icon_ref` 格式为 `tdesign:<icon-name>`
  - `minor_visible`：是否青少年可见（默认 `false`）
  - `review_visibility_scope` 枚举：
    - `0=ALL_USERS`
    - `1=REGULAR_USERS`
    - `2=ALL_REVIEWERS`
    - `3=MP_WEIXIN_REVIEWERS`

### 上架表

- 表：`square_type_entries`
- 字段：`category_key`、`type_id`、`exposure_strategy`、`status`
- 约束：
  - `(category_key, type_id)` 唯一

## 分类曝光规则

- 分类接口仅返回 `square_categories.status=active` 的记录。
- 分类排序为 `sort_order ASC`，其次 `category_key ASC`。
- 分类接口按 `review_visibility_scope` 过滤：
  - `review_scope=NON_REVIEW`：`ALL_USERS + REGULAR_USERS`
  - `review_scope=MP_WEIXIN_REVIEW`：`ALL_USERS + ALL_REVIEWERS + MP_WEIXIN_REVIEWERS`
- 当用户开启青少年模式时，额外叠加 `minor_visible=true` 过滤（与 `review_visibility_scope` 取交集）。

## 列表查询规则

- Square 联系人列表按 `category_key` 维度查询。
- `category_key` 必须属于当前用户可见分类集合。
- 列表筛选目标分类下 ACTIVE 的上架记录并映射到 `type_id` 集。
- 列表分页使用 `cursor`。
- 刷新请求使用 `refresh=true` 并生成新 `feed_version`。
- 加载更多请求使用 `feed_version + cursor` 继续读取同一列表版本。
- 每条联系人卡片回传 `category_key` 用于来源回显。
- 限流按动作拆分为“刷新”和“加载更多”两组。
- `refresh_available_at` 仅用于刷新节奏控制。

## Persona 选择与展示字段

- Square 展示对象为 `ai_personas`。
- 通过 `square_type_entries.type_id` 选取候选 persona。
- 候选 persona 需要满足：
  - `ai_personas.status=active`
  - persona 的 `type_id` 在目标分类的 ACTIVE 上架 `type_id` 集内
  - persona 的 `qiao_id` 不在当前用户历史添加集合内（`contacts`，含已删除记录）
- 同一分类同一 `feed_version` 内，`qiao_id` 不重复。
- 随机策略为类型均衡随机。
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
- 未传入、无效、下线或当前用户不可见分类时，`category_key` 与 `category_title` 返回 `null`。
- 同时返回 `tags` 与 `remark`，规则见：`docs/spec/contact/ai-creation.md` - tags 写入规则
