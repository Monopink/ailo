# 小程序访问门控与 Demo 隔离重构方案

生效日期：2026-04-30

## 目标

- 审核相关能力与正常生产链路解耦，生产页面恢复单一登录守卫模型。
- 离线审核窗口与在线未登录审核入口统一使用独立本地 Demo 页面体系。
- `square-demo` 作为常规入口与常规页面长期保留，`暂不登录` 入口始终可用。
- 登录提示文案与跳转机制全局统一，移除分叉实现。
- `square` 生产页面移除模拟兜底数据，改为标准加载/错误表现。

## 实施范围

- 小程序启动路由与访问门控决策链路。
- 小程序登录守卫、登录失效处理、需要登录的交互拦截。
- `square-entry`、`square`、`square-demo` 及其数据源。
- 邀请能力在审核登录态下的可见性控制链路。

## 状态模型

启动阶段统一收敛为以下四态：

- `ONLINE_REVIEW_GUEST`：在线、未登录、服务端 `access_gate_open=true`。
- `OFFLINE_REVIEW_DEMO`：离线、未登录、构建时间后 36 小时内。
- `ONLINE_REVIEW_AUTH`：在线、已登录、`review_scope=1`（映射为受限账号能力）。
- `NORMAL`：除上述情况外的常规生产状态。

## 路由与页面策略

### 启动路由

- `ONLINE_REVIEW_GUEST` -> `/pkg/square-demo/square-demo`
- `OFFLINE_REVIEW_DEMO` -> `/pkg/square-demo/square-demo`
- `ONLINE_REVIEW_AUTH` -> 生产链路（标准页面），并应用受限能力可见性
- `NORMAL` -> 已登录进入生产链路；未登录默认进入 `/pages/login/login`

### 标准页面守卫

- 生产页面恢复标准登录守卫：未登录不可访问。
- 未登录访问生产页面时统一触发同一登录引导机制，不保留页面级分叉文案。

### Demo 页面体系

- `square-demo` 作为独立入口页，承载审核未登录与离线窗口浏览。
- `square-demo` 在非审核周期也可访问，登录页 `暂不登录` 按钮始终可进入 `square-demo`。
- 增加本地 mock 子页用于基础功能浏览。
- Demo 体系不发消息、不加好友、不调用生产业务写接口。
- 仅 `OFFLINE_REVIEW_DEMO` 状态启用离线 mock 环境；其他状态进入 `square-demo` 仅用于常规浏览入口。

### 离线恢复在线

- Demo 状态下检测到可连通服务器时，统一 `reLaunch` 到 `/pages/boot/boot`。
- 由 `boot` 重新探测并按最新服务端配置重路由。

## 登录提示与跳转统一

- 统一登录提示文案：`请先登录后继续`。
- 统一跳转机制：通过同一个登录引导入口执行跳转到 `/pages/login/login`。
- `requireAuth`、401 失效处理、Demo 页面按钮拦截全部复用该入口。
- 登录页 `暂不登录` 入口不受在线/离线、审核周期影响，始终展示且可点击。

## 生产 `square` 数据策略

- 移除生产 `square` 的模拟兜底数据与预览模式分支。
- 页面表现统一为：
  - 加载中：Skeleton
  - 请求失败：Error + Retry
  - 请求成功无数据：Empty

## 邀请能力策略

- 邀请能力由账号能力统一控制（`review_scope -> account_segment` 映射后判定）。
- 审核登录态（受限能力）下邀请入口与邀请相关文案统一隐藏或不可达。
- 普通生产态维持现有邀请能力展示与功能。

## 代码收敛要求

- 删除生产页面中的 `demo_public` / `demo_offline_window` 分支逻辑。
- 删除 `square-preview-data` 在生产链路中的引用。
- 删除多套登录提示文案与分叉跳转实现。
- 不引入兼容层，不保留历史链路开关。

## 影响文件清单

- `frontend/mp-weixin/pages/boot/boot.ts`
- `frontend/mp-weixin/utils/auth-guard.ts`
- `frontend/mp-weixin/utils/auth-expired-modal.ts`
- `frontend/mp-weixin/utils/client-access-mode.ts`
- `frontend/mp-weixin/pages/square-entry/square-entry.ts`
- `frontend/mp-weixin/pkg/square/square.ts`
- `frontend/mp-weixin/utils/discovery-service.ts`
- `frontend/mp-weixin/utils/square-preview-data.ts`
- `frontend/mp-weixin/pkg/square-demo/*`
- `frontend/mp-weixin/app.ts`
- `frontend/mp-weixin/app.json`

## 验收标准

- 在线未登录且服务端审核期开启时，启动后直接进入 `square-demo`。
- 离线且处于 36 小时窗口时，启动后直接进入 `square-demo`。
- 非审核周期未登录启动时，默认进入 `/pages/login/login`。
- 登录页 `暂不登录` 入口在在线/离线、审核期/非审核期均可进入 `square-demo`。
- Demo 状态恢复连通后自动回 `boot`，并按服务端配置进入最新状态链路。
- 生产页面未登录访问统一提示同一文案并走同一跳转机制。
- `square` 页面无模拟兜底数据；失败时展示错误态并可重试。
- 审核登录态下邀请能力入口不可见或不可达。

## 实施结果记录

- 已完成启动路由重构：审核未登录与离线 36 小时窗口自动进入 `square-demo`，非审核未登录默认进入登录页。
- 已完成登录提示收敛：新增统一登录引导工具，`requireAuth` 与会话失效处理复用同一文案和跳转机制。
- 已完成生产页面去 preview 分支：`square-entry` 与 `square` 不再承载未登录预览逻辑。
- 已完成离线 Demo 子页落地：新增 `demo-chat`、`demo-profile`、`demo-contact` 本地浏览页并接入 `square-demo` 离线入口。
- 已完成离线恢复在线回跳：在 `square-demo` 离线入口恢复连通后自动 `reLaunch` 到 `boot` 重算状态。
- 已完成前端校验：`npm run check` 全量通过。
