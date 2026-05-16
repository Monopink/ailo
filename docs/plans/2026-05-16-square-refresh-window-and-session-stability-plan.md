# 2026-05-16 Square 刷新窗口与会话稳定性方案

## 文档状态

- 状态：待实施
- 创建日期：`2026-05-16`
- 适用范围：`pkg/square/square`、`pkg/stranger-info/stranger-info`、`/api/v1/discovery/square`、Discovery 相关配置与状态存储

## 目标

1. Square 页面仅在冷进入触发远程刷新，热恢复保持列表与滚动状态。
2. Discovery 刷新机制改为服务端状态驱动，按用户+分类维度执行刷新窗口控制。
3. Discovery 分页按 feed 维度限制最大页数，并返回明确的分页结束语义。
4. 发送联系人请求后，Square 列表立即移除目标项，不触发整页刷新。

## 需求点

1. 去除 Square 内容区下拉刷新入口。
2. 从 `pkg/stranger-info/stranger-info` 返回 `pkg/square/square` 时，页面保持原数据与原位置。
3. 每个分类独立执行刷新间隔控制，刷新间隔为 2 小时，配置化管理。
4. Square 顶部展示刷新倒计时与下次刷新时间。
5. 每个分类每个 feed 最多加载 3 页，配置化管理。
6. 到达分页上限时，列表底部展示“已经到底啦”。

## 实施范围

### 后端与数据层

1. 新增 `square_user_category_state` 持久状态表，唯一键为 `(user_qiao_id, category_key)`。
2. 新增 `system_configs` 配置键：
   - `square_refresh_interval_seconds`（默认 `7200`）
   - `square_max_pages_per_feed`（默认 `3`）
3. `GET /api/v1/discovery/square` 移除 `refresh` 请求参数，改为服务端按状态决定 feed 刷新。
4. 升级 cursor 契约，携带并校验 `page_index`，服务端强约束 feed 最大页数。

### API 契约

1. `GET /api/v1/discovery/square` 响应新增并始终返回刷新状态字段：
   - `can_refresh_now`
   - `refresh_remaining_seconds`
   - `next_refresh_available_at`
   - `refresh_interval_seconds`
2. 响应新增分页控制字段：
   - `current_page_index`
   - `max_pages_per_feed`
   - `end_reason`

### 客户端行为

1. `pkg/square/square` 仅在页面实例首次进入触发远端加载。
2. `pkg/square/square` 热恢复场景禁止自动刷新与滚动重置。
3. `pkg/square/square` 发送联系人请求成功后，立即从当前页面内全部分类结果移除该 `qiao_id`。
4. `pkg/square/square` 使用响应刷新状态字段驱动顶部 info-bar 展示。
5. `pkg/square/square` 到达分页上限时展示固定底部文案“已经到底啦”。

## 文档对齐任务

1. 更新 `docs/api/discovery.md` 的广场联系人接口契约。
2. 更新 `docs/spec/client/base/discovery.md` 的页面行为规范。
3. 更新 `docs/spec/client/mini-program/service-layer.md` 的页面加载策略。
4. 更新 `docs/spec/contact/square.md` 的列表查询与分页规则。

## 验收标准

1. Square 热恢复不触发远程刷新，返回后列表内容与滚动位置保持一致。
2. Square 冷进入会触发远程加载并更新当前分类列表。
3. 广场联系人接口不再接收 `refresh` 参数，响应始终包含刷新状态字段。
4. 每个分类每个 feed 超过 3 页请求时，服务端返回分页结束语义，客户端展示“已经到底啦”。
5. 发送联系人请求成功后，目标 `qiao_id` 在当前 Square 页面内不再显示。
