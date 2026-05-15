# 2026-05-15 Square 列表滚动契约对齐计划

## 文档状态

- 状态：已实施
- 创建日期：`2026-05-15`
- 最后更新：`2026-05-15`
- 适用范围：小程序 `page-layout` 组件、`pkg/square/square` 页面、发现页相关规范文档

## 目标

1. 为 `page-layout` 建立统一的内容滚动事件契约，支持触底分页与下拉刷新。
2. 让 `pkg/square/square` 的分页加载与刷新链路完整闭环。
3. 保持发现页规范、UI 规范与组件契约一致。

## 问题点（现态）

1. `page-layout` 内容区使用内部 `scroll-view` 承载滚动，但未对外暴露触底与刷新事件。
2. `pkg/square/square` 使用页面生命周期 `onReachBottom` / `onPullDownRefresh` 触发分页与刷新，无法接收 `page-layout` 内部滚动事件。
3. 发现页规范与 UI 规范在滚动触发机制上描述不一致。

## 实施范围

### 组件契约

1. 在 `page-layout` 中定义内容区滚动事件契约：
   - `contentreachbottom`：内容区触底事件。
   - `contentrefresh`：内容区下拉刷新事件。
2. 在 `page-layout` 中定义滚动参数契约：
   - `lowerThreshold`：触底阈值。
   - `enableContentRefresh`：内容区下拉刷新开关。

### Square 页面接入

1. `pkg/square/square.wxml` 监听 `page-layout` 的 `contentreachbottom` 与 `contentrefresh` 事件。
2. `pkg/square/square.ts` 将触底与刷新逻辑统一接入 `loadContacts`：
   - 触底事件触发 `mode='load_more'`
   - 刷新事件触发 `mode='refresh'`
3. 页面不再依赖生命周期滚动事件作为列表分页入口。

### 文档对齐

1. 更新 `docs/spec/client/mini-program/ui.md`，声明 `page-layout` 的滚动与刷新契约入口。
2. 更新 `docs/spec/client/base/discovery.md`，将发现页列表分页与刷新触发方式对齐到 `page-layout` 内容事件。
3. 新增 `docs/spec/client/mini-program/page-layout.md`，作为组件契约单一真相源。

## 实施任务

1. 组件：扩展 `frontend/mp-weixin/components/page-layout/page-layout.ts`、`page-layout.wxml`、`page-layout.json`，提供事件与属性契约。
2. 页面：修改 `frontend/mp-weixin/pkg/square/square.wxml`、`square.ts`，接入新契约并清理无效触发路径。
3. 验证：运行 `frontend/mp-weixin` 下 `npm run check`，并验证触底分页与下拉刷新行为。
4. 文档：同步更新 `docs/spec/client/mini-program/page-layout.md`、`docs/spec/client/mini-program/ui.md`、`docs/spec/client/base/discovery.md`。

## 验收标准

1. `pkg/square/square` 在存在下一页时，触底可连续触发 `load_more` 请求并追加列表数据。
2. `pkg/square/square` 下拉刷新触发 `refresh=true` 请求并更新 `feed_version`。
3. `page-layout` 的滚动与刷新事件契约被页面稳定消费，滚动行为与页面状态模型一致。
4. 发现页与 UI 规范文档描述一致，且与代码行为一致。

## 实施结果

1. `page-layout` 已提供 `contentreachbottom`、`contentrefresh`、`contentscroll`、`contentrefresherrestore` 事件。
2. `page-layout` 已增加 `lowerThreshold` 与 `enableContentRefresh` 属性，并使用 `refreshState` 驱动刷新态。
3. `pkg/square/square` 已改为通过组件事件驱动分页与刷新。
4. 发现页与小程序 UI 规范已对齐当前路由与滚动契约。
5. 小程序验证已通过：`npm run check`。
