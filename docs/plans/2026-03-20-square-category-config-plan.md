# Square 分类可配置化方案（category_key）

## 目标

- Square 分类从硬编码数值枚举改为服务端可配置。
- 小程序分类与分类展示信息由后端动态下发。
- 管理后台支持分类配置（标题、描述、主题、图标、排序、上下线）。
- discovery 与 contact request 相关文档、数据字典、初始化脚本与实现保持一致。

## 范围

- 后端：数据模型、API、管理后台（Starlette Admin）字段与校验。
- 小程序：`square-entry`、`square`、`stranger-info` 分类上下文与降级。
- 文档：`docs/api/*`、`docs/spec/*`、`docs/data-dict/*` 相关章节。
- 初始化脚本：`backend/database/init/sql/*` 中相关表结构与样例数据。

## 非目标

- 不实现“根据分类自动打标签”。
- 不实现 COS/CDN 图标资源管理（仅支持 `tdesign:<icon-name>`）。
- 不保留旧 `int category` 输入与响应（不做向后兼容）。

## 决策（已确认）

- 分类对外标识为 `category_key`（kebab-case），创建后不可修改。
- `square_categories` 使用内部数值主键 `id`，`category_key` 为唯一外部键。
- `GET /api/v1/discovery/square-categories` 需要鉴权，且只返回 active 非空壳分类。
- `GET /api/v1/discovery/square` 必填 `category_key`，不提供 all 模式。
- `GET /api/v1/discovery/square` 返回 `items + pagination + refresh_available_at`。
- `GET /api/v1/discovery/profile/{qiao_id}` 支持可选 `category_key`，返回 `category_key + category_title`；`category_key` 无效或下线时返回 `null`。
- `contact_requests` 持久化 `category_key`、`alias`、`tags`，创建与幂等更新路径均写入。
- `square_type_entries` 对同一 `type_id` 采用“仅 ACTIVE 唯一”约束。
- `icon_ref` 使用 `tdesign:<icon-name>`；客户端渲染失败时默认 `tdesign:chat`。
- `theme_key` 值域固定：`ocean`、`sky`、`mint`、`forest`、`lime`、`amber`、`sunset`、`rose`、`grape`、`slate`。
- `square-entry` 进入即鉴权，未登录不进入广场流程。
- 小程序收到不可用 `category_key` 时静默回到 Square 入口页。

## 数据模型改造

### 新表：`square_categories`

- 字段：
  - `id`（bigint PK）
  - `category_key`（varchar，UNIQUE）
  - `title`（varchar）
  - `description`（text，nullable）
  - `theme_key`（varchar）
  - `icon_ref`（varchar）
  - `sort_order`（int）
  - `status`（int，1=active，2=inactive）
  - `created_at`、`updated_at`
- 约束：
  - `category_key` 正则：`^[a-z0-9]+(?:-[a-z0-9]+)*$`
  - `theme_key` 受限于固定 10 个值
  - `icon_ref` 正则：`^tdesign:[a-z0-9-]+$`
  - `category_key` 不可修改（服务端与后台写入路径禁改）

### 变更：`square_type_entries`

- 字段替换：`square_category (int)` -> `category_key (string FK -> square_categories.category_key)`。
- 约束：
  - `(category_key, type_id)` 唯一。
  - `type_id` 在 `status=ACTIVE` 条件下唯一（部分唯一索引）。

### 变更：`contact_requests`

- 新增字段：
  - `category_key`（nullable string）
  - `alias`（nullable string）
  - `tags`（nullable jsonb）
- 写入路径：
  - 新建请求写入上述字段。
  - 幂等更新（pending/processing）同步覆盖上述字段。

## API 改造

### 新增：`GET /api/v1/discovery/square-categories`

- 鉴权：Bearer Token。
- 返回：`items[]` 包含 `category_key`、`title`、`description`、`theme_key`、`icon_ref`。
- 过滤：`status=active` 且分类下存在 ACTIVE 的 `square_type_entries`。
- 排序：`sort_order ASC`，`category_key ASC`。

### 修改：`GET /api/v1/discovery/square`

- 入参：`category_key`（必填）、`page`、`page_size`。
- 返回：
  - `items[]`：联系人字段 + `category_key`。
  - `pagination`：分页信息。
  - `refresh_available_at`：下次允许刷新时间。
- 限流 key：`user_qiao_id + category_key`。

### 修改：`GET /api/v1/discovery/profile/{qiao_id}`

- 入参：可选 `category_key`。
- 返回：
  - 现有 profile 字段。
  - `category_key`、`category_title`。
  - 未传入、无效或下线分类均返回 `category_key=null`、`category_title=null`。

### 修改：`POST /api/v1/contact-requests`

- 入参新增：可选 `category_key`、`alias`、`tags`。
- 行为：持久化到 `contact_requests`，用于异步 worker 上下文。

## 管理后台改造

- 新增 `square_categories` 管理页：
  - 创建、编辑（禁改 `category_key`）、上下线、排序。
  - `theme_key` 仅允许固定值。
  - `icon_ref` 录入并校验 `tdesign:<icon-name>` 格式。
- 改造 `square_type_entries` 管理页：
  - 分类字段改为 `square_categories` 选择。
  - 创建/编辑校验 ACTIVE 条件下 `type_id` 唯一。

## 小程序改造

### 分类缓存

- 分类缓存：`square_categories_v1`，结构 `{ items, timestamp }`。
- Square 列表缓存：`square_<category_key>`。

### `pages/square-entry/square-entry`

- 页面进入执行鉴权。
- 渲染顺序：
  1. 有分类缓存先渲染缓存。
  2. 无缓存渲染内置默认卡片。
  3. 后台请求 `square-categories`，成功后刷新缓存与 UI。
- 点击分类：
  - 请求失败时，若存在该分类列表缓存则允许进入列表页；
  - 无缓存则提示并停留入口页。

### `pages/square/square`

- Tab 来源于分类接口（缓存优先，后台刷新）。
- `category_key` 缺失、无效、下线时静默 `switchTab` 回入口页。
- 列表缓存按 `category_key` 维度读取与写入。

### `pages/stranger-info/stranger-info`

- 从 Square 进入时透传 `category_key`。
- 拉取 `/discovery/profile/{qiao_id}` 时附带 `category_key`。
- 分类文案使用响应 `category_title`。

## 迁移步骤

1. 新建 `square_categories` 表与相关约束、索引。
2. 写入初始分类：`friend`、`love`、`talk`、`bestie`、`hobby`。
3. 迁移 `square_type_entries.square_category` 到 `category_key`。
4. 建立 `square_type_entries` 的 ACTIVE 唯一约束。
5. 在 `contact_requests` 增加 `category_key`、`alias`、`tags` 字段。
6. 切换后端入参校验、响应模型、后台字段配置到新结构。
7. 切换小程序接口入参与缓存 key 到 `category_key`。
8. 移除旧数值分类依赖并同步文档。

## 文档对齐清单

- `docs/api/discovery.md`
- `docs/api/contact-requests.md`
- `docs/spec/contact/square.md`
- `docs/spec/client/base/discovery.md`
- `docs/data-dict/discovery.md`
- `docs/data-dict/contact.md`

## 验证清单

- 后台：
  - 分类可创建、编辑、上下线、排序。
  - `category_key` 不可编辑。
  - ACTIVE 条件下同一 `type_id` 只能存在一条上架记录。
- 客户端：
  - 入口页无缓存不空白。
  - 离线时按缓存策略进入或提示。
  - 无效 `category_key` 静默回入口页。
  - 陌生人页分类文案来自 `category_title`。
  - 非法 `icon_ref` 使用默认图标。
- 后端：
  - `square-categories` 过滤与排序正确。
  - `square` 的必填入参、分页、冷却时间字段、限流 key 正确。
  - `profile` 的 `category_key/category_title` 回显规则正确。
  - `contact-requests` 创建与幂等更新均写入 `category_key/alias/tags`。
