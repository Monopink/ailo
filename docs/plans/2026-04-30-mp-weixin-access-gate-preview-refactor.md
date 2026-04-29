# 小程序访问门控与 Preview 页面重构方案

生效日期：2026-04-30

## 目标

- `square-demo` 固定为常规「暂不登录」页面，作为全时段可用入口。
- 审核模式仅影响启动默认落点，不改变常规入口能力。
- 离线且处于审核窗口时，进入独立 `preview-*` 页面体系，使用「游客身份」语义与本地模拟数据。
- 生产页面保持标准登录守卫与标准业务链路，不承载离线审核模拟逻辑。

## 路由判定矩阵

启动入口统一为 `/pages/boot/boot`，按连接状态、审核周期、登录状态判定：

- 在线 + 审核期 + 未登录：`/pkg/square-demo/square-demo`
- 在线 + 审核期 + 已登录：生产页面链路
- 在线 + 非审核期 + 未登录：`/pages/login/login`
- 在线 + 非审核期 + 已登录：生产页面链路
- 离线 + 审核窗口内（构建后 36 小时内）+ 未登录：`/pkg/preview-index/preview-index`
- 离线 + 审核窗口内（构建后 36 小时内）+ 已登录：`/pkg/preview-index/preview-index`
- 离线 + 非审核期或超出 36 小时 + 未登录：`/pages/login/login`
- 离线 + 非审核期或超出 36 小时 + 已登录：生产页面链路（按现有降级能力处理）

## 页面职责清单

- `pages/boot/boot`：唯一启动决策器，仅执行状态探测与一次性路由，不承载业务展示。
- `pages/login/login`：正常未登录入口，保留「暂不登录」按钮并跳转 `square-demo`。
- `pkg/square-demo/square-demo`：常规未登录浏览页，全时段可手动访问。
- `pkg/preview-index/preview-index`：离线审核主入口与导航壳。
- `pkg/preview-square/preview-square`：离线审核广场浏览页（本地数据）。
- `pkg/preview-chat/preview-chat`：离线审核会话浏览页（本地数据、本地操作）。
- `pkg/preview-contact/preview-contact`：离线审核联系人浏览页（本地数据、本地操作）。
- `pkg/preview-profile/preview-profile`：离线审核个人资料页（游客身份语义）。
- 生产页面（`pages/*`、`pkg/square/*` 等）：保持正常业务链路，不引入审核离线分叉。

## Preview 数据与交互约束

- 统一使用「游客身份」语义填充信息，例如游客昵称、游客资料、游客会话。
- Preview 页面数据全部来自本地 mock 数据层。
- Preview 页面交互全部为本地模拟操作，不调用生产业务写接口。
- Preview 页面不出现「登录查看更多」「去登录」等登录引导文案。

## 连通性恢复规则

- 处于 `preview-*` 页面时检测到恢复连通，统一 `reLaunch('/pages/boot/boot')`。
- 恢复在线后的落点由 `boot` 按服务端配置与登录态重新判定。

## 实施范围

- 小程序启动路由与访问门控决策链路。
- `square-demo` 角色收敛与离线审核分离。
- `preview-*` 页面体系重建（`index/square/chat/contact/profile`）。
- 本地 mock 数据层与本地模拟交互实现。
- 离线恢复在线回跳机制。

## 影响文件清单

- `frontend/mp-weixin/pages/boot/boot.ts`
- `frontend/mp-weixin/pages/login/login.ts`
- `frontend/mp-weixin/pkg/square-demo/*`
- `frontend/mp-weixin/pkg/preview-index/*`
- `frontend/mp-weixin/pkg/preview-square/*`
- `frontend/mp-weixin/pkg/preview-chat/*`
- `frontend/mp-weixin/pkg/preview-contact/*`
- `frontend/mp-weixin/pkg/preview-profile/*`
- `frontend/mp-weixin/utils/preview-mock/*`
- `frontend/mp-weixin/app.ts`
- `frontend/mp-weixin/app.json`

## 验收标准

- `square-demo` 在在线/离线、审核期/非审核期均可通过「暂不登录」入口访问。
- 在线审核期未登录启动时默认进入 `square-demo`。
- 离线且构建后 36 小时窗口内启动时默认进入 `preview-index`。
- `preview-*` 页面展示游客身份语义，功能交互为本地模拟，不触发生产写接口。
- `preview-*` 页面不出现登录引导文案。
- `preview-*` 状态恢复在线后自动回到 `boot` 并按在线规则重路由。
- 生产页面登录守卫行为、业务数据链路与邀请能力控制保持既定行为。
