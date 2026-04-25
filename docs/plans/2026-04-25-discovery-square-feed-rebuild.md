# 发现页多分类绑定与随机 Feed 重构方案

## 目标

- 将发现页分类与 AI 类型关系定义为多对多。
- 将发现页列表改为可持续下滑加载的随机 Feed，支持稳定分页与刷新重排。
- 将发现页排除规则定义为“用户历史添加记录永久排除”，覆盖已删除联系人。
- 统一后端接口契约、小程序缓存策略与限流策略。

## 已确认决策

- 历史添加排除：追溯历史数据，`contacts` 中该用户对目标 `qiao_id` 的记录均参与排除判定（含 `is_deleted=1`）。
- 误删回找：发现页对已添加目标永久不可见。
- 跨分类重复：允许同一 persona 在不同分类中曝光；同一分类内去重。
- 随机策略：采用类型均衡随机。
- 分页策略：采用 `cursor`，默认 `page_size=20`，支持持续加载。
- 限流策略：拆分刷新限流与加载更多限流。
- 缓存策略：小程序缓存键包含 `user + category + feed_version`。
- 接口切换：一次切换到新契约，不保留旧分页语义。

## 现状

- `square_type_entries` 当前存在 `(category_key, type_id)` 唯一约束与 active `type_id` 唯一约束。
- 发现页后端查询以 `ORDER BY random()` + `page/offset` 返回结果。
- 发现页排除逻辑仅过滤 `contacts.is_deleted=0` 的联系人关系。
- 小程序发现页仅请求 `category_key`，未携带 `page`，页面未实现 `onReachBottom` 加载下一页。
- 限流按 `user_qiao_id + category_key` 统一生效，刷新与持续加载共用一套限制。

## 问题点

- active `type_id` 唯一约束与多分类绑定目标冲突。
- `random()+offset` 无法保障随机 Feed 的稳定分页、去重与性能。
- 排除逻辑与“历史添加永久排除”目标冲突。
- 刷新与持续加载共用限流会压缩正常浏览动作。
- 小程序缓存缺少 `feed_version` 维度，无法表达刷新重排语义。

## 方案范围

本次方案覆盖：

- `square_type_entries` 关系约束调整。
- 发现页候选集构建、随机排序、`cursor` 分页、历史添加排除。
- 发现页 API 契约调整。
- 发现页刷新/加载更多限流拆分。
- 小程序发现页 service 与页面交互改造。
- 发现页链路观测字段补齐与回归验证。

本次方案不覆盖：

- 发现页以外入口页的陌生人曝光改造。
- A/B 分流与多实验策略系统。

## 数据与查询设计

### 1) 分类与类型绑定

- 保留唯一约束：`(category_key, type_id)`。
- 移除 active `type_id` 全局唯一约束。
- 继续使用 `status=active` 作为可曝光记录筛选条件。

### 2) 候选集定义

候选 persona 集合满足以下条件：

- persona 属于请求分类绑定的 `type_id` 集。
- persona 处于可用状态。
- persona `qiao_id` 未出现在该用户历史添加集合内（历史集合来源：`contacts`，不按 `is_deleted` 过滤）。

### 3) 随机与分页

- 引入 `feed_version`，由刷新动作生成。
- 在同一 `feed_version` 内，排序键使用“用户维度确定性随机”并保持稳定。
- 列表接口使用 `cursor` 分页，返回 `next_cursor` 与 `has_more`。
- 同一分类同一 `feed_version` 内，`qiao_id` 仅出现一次。
- 类型均衡随机策略按批次控制同一 `type_id` 曝光上限，避免集中。

## API 契约

### `GET /api/v1/discovery/square`

- 请求参数：
  - `category_key` (required)
  - `cursor` (optional)
  - `page_size` (optional, default 20, max 50)
  - `refresh` (optional, boolean)
- 响应字段：
  - `items`
  - `feed_version`
  - `next_cursor`
  - `has_more`
  - `refresh_available_at`

行为定义：

- `refresh=true`：生成新 `feed_version`，返回该版本首批数据。
- `refresh=false` 且传入 `cursor`：在指定 `feed_version` 上继续加载。
- `refresh_available_at` 仅用于刷新动作节奏控制。

## 限流设计

- 新增刷新限流组：约束 `refresh=true` 请求频率。
- 新增加载更多限流组：约束 `cursor` 连续加载请求频率。
- 刷新与加载更多分别配置系统参数并分别返回节流语义。

## 小程序设计

### 1) Service 层

- `discovery-service` 增加 `feed_version`、`cursor`、`has_more` 状态管理。
- 缓存键升级为 `square_{user_qiao_id}_{category_key}_{feed_version}`。
- 分类切换、刷新、持续加载三类请求分别调用对应参数组合。

### 2) 页面交互

- `pages/square/square` 实现 `onReachBottom` 触发持续加载。
- 下拉刷新触发 `refresh=true`。
- 刷新限流命中时保留当前列表并展示等待秒数。
- 持续加载限流命中时不清空当前内容，仅提示加载节奏。

## 观测与验证

发现页链路记录以下观测字段：

- `candidate_count`
- `excluded_history_count`
- `returned_count`
- `duplicate_filtered_count`
- `query_duration_ms`
- `feed_version`

## 实施步骤

1. 更新方案文档（本文件）并冻结实施口径。
2. 编写 Alembic 迁移：移除 active `type_id` 唯一索引，补齐查询索引。
3. 同步后端 model/admin 约束处理逻辑。
4. 重构 discovery data/service：候选集、历史添加排除、确定性随机、`cursor` 分页。
5. 更新 discovery API schema 与路由参数处理。
6. 拆分限流配置键与限流检查逻辑。
7. 改造小程序 `discovery-service`、`square-service`、`pages/square/square`。
8. 联调并执行后端/前端验证与回归。
9. 更新 `docs/api/discovery.md`、`docs/spec/contact/square.md`、`docs/spec/client/base/discovery.md` 为当前有效状态。

## 验收标准

- 一个 `type_id` 可同时出现在多个 active 分类中。
- 发现页接口返回 `feed_version + next_cursor + has_more`，分页稳定。
- 同一分类同一 feed 版本内无重复 persona。
- 用户历史添加过的 persona 在发现页不可见（含已删除联系人）。
- 小程序支持下滑持续加载，刷新动作与加载更多动作限流策略独立生效。
- 缓存按 `user + category + feed_version` 生效，刷新后读取新版本缓存。

## 影响文件（实施阶段）

- `backend/alembic/versions/*.py`
- `backend/app/models/content/__init__.py`
- `backend/app/services/discovery/data.py`
- `backend/app/services/discovery/service.py`
- `backend/app/api/v1/discovery.py`
- `backend/app/schemas/discovery.py`
- `backend/app/services/security/rate_limiter.py`
- `backend/database/bootstrap/base.sql`
- `frontend/mp-weixin/utils/discovery-service.ts`
- `frontend/mp-weixin/pkg/services/pages/square-service.ts`
- `frontend/mp-weixin/pkg/square/square.ts`
- `docs/api/discovery.md`
- `docs/spec/contact/square.md`
- `docs/spec/client/base/discovery.md`

## 实施结果

- 当前状态：已实施完成。
