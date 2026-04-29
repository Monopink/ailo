# 小程序审核访问门控与 Preview 统一重构方案

生效日期：2026-04-30

## 目标

- 审核访问门控采用单一 Preview 页面体系，入口、导航、交互与数据语义统一。
- Preview 页面视觉和结构与正式页面保持一致的设计语言，页面可浏览、可操作、链路闭环。
- 连通性事件上报具备去噪、去重、限流与可追踪能力，满足审核排障需要。
- 账号审核分段在冷启动流程内完成同步，能力控制一致生效。

## 范围

- 小程序启动路由与审核访问门控。
- `preview-*` 页面体系（`index/square/chat/contact/profile`）与样式复用策略。
- 小程序连通性事件上报链路（客户端与服务端）。
- 账号审核分段同步链路与邀请能力可见性控制链路。

## 强制决策

### 1. Preview 入口统一

- 在线未登录且服务端审核期开启：进入 `/pkg/preview-index/preview-index`。
- 离线且构建时间后 36 小时窗口内：进入 `/pkg/preview-index/preview-index`。
- 登录页“暂不登录，先看看”：进入 `/pkg/preview-index/preview-index`。
- `square-demo` 不承载审核访问门控入口职责。

### 2. 连通性事件上报策略

- 默认禁报成功事件，仅上报异常事件。
- 上报去重窗口：每设备 + 每 build + 每 24 小时一次。
- 去重指纹字段：
  - `client_type`
  - `device_id`
  - `build_id`
  - `reason_code`
  - `review_mode_local_decision`
  - `review_mode_server_decision`
  - `network_type`
  - `day_bucket`（UTC 日粒度）

### 3. Preview 数据语义

- Preview 模式按“新注册账号”语义提供内容。
- 联系人与会话允许为空。
- 广场提供最小可浏览分类与列表数据。

### 4. 账号分段生效策略

- “无需重新登录立即生效”不作为本次强制目标。
- 冷启动时完成分段同步并应用能力控制。

## 状态模型

- `PREVIEW_GUEST`：未登录，且满足审核访问门控条件。
- `AUTH_MEMBER_LIMITED`：已登录且审核账号分段。
- `AUTH_MEMBER_FULL`：已登录且普通账号分段。
- `LOGIN_REQUIRED`：未登录且不满足审核访问门控条件。

## 路由规则

- `PREVIEW_GUEST` -> `/pkg/preview-index/preview-index`
- `AUTH_MEMBER_LIMITED` -> 生产页面链路（邀请能力隐藏）
- `AUTH_MEMBER_FULL` -> 生产页面链路
- `LOGIN_REQUIRED` -> `/pages/login/login`

## 架构方案

### 1. Preview 页面复用方案

- `preview-index` 复用正式 `index` 页面结构层与核心样式变量，保持头部、列表、空态、底部栏布局一致。
- `preview-square` 复用正式 `square` 页面布局结构，替换为 Preview 数据源。
- `preview-profile` 复用正式 `profile` 页面结构层，保留 Preview 导航闭环。
- `preview-chat` 与 `preview-contact` 保留 Preview 专属交互层，视觉 token 与 spacing 对齐正式页面。
- Preview 页面统一引入 `preview-pages.wxss`，统一底部栏、基础容器与通用交互样式。

### 2. Preview 数据层

- 保留单一 `preview-mock/data.ts` 作为 Preview 数据源。
- 提供最小广场浏览数据（分类 + 列表）。
- 会话、消息、联系人支持空集合并保持页面可用。
- 清理未引用的 Preview 数据分支文件，数据源唯一化。

### 3. 连通性事件治理

- 客户端：
  - 仅在异常分支触发上报。
  - 以去重指纹 + UTC `day_bucket` 进行本地去重缓存。
  - 去重命中则跳过请求。
- 服务端：
  - 请求校验：`device_id` 为空直接拒绝。
  - 幂等去重：按去重指纹 + `day_bucket` 约束写入一次。
  - 限流：按 `device_id + build_id` 设置日配额与短时频控。
  - 入库仅保留排障必需字段，过滤无价值内容。

### 4. 分段同步链路

- 登录接口返回分段字段作为首次写入来源。
- `GET /user/profile` 响应补充分段字段，作为冷启动校准来源。
- `authService.initialize()` 以服务端分段覆盖本地分段，写回 `USER_INFO`。

## 实施任务

1. 路由收敛
   修改 `boot` 与 `login` 路由分支，统一 Preview 入口到 `preview-index`。

2. Preview 页面结构与样式收敛
   修复 `preview-index`、`preview-profile` 样式依赖缺失；统一通用样式导入；对齐正式页面结构层。

3. Preview 数据最小闭环
   在 `preview-mock/data.ts` 提供广场最小浏览数据；联系人/会话空态可用；清理未引用数据分支。

4. 连通性上报治理实现
   客户端完成异常上报 + 本地 24 小时去重；服务端完成幂等去重、限流、空设备拦截。

5. 分段同步完善
   打通登录返回与 profile 返回分段字段；冷启动覆盖写回；能力控制链路统一读取分段结果。

6. 文档同步
   同步更新 `docs/spec/client/mini-program/*` 与 `docs/api/client.md`、`docs/api/auth.md`、`docs/api/users.md` 的当前有效行为描述。

## 验收标准

- 审核访问门控所有未登录入口统一进入 `preview-index`。
- `preview-index` 与 `preview-profile` 底部栏布局稳定，视觉与正式页面一致性符合基线。
- Preview 模式下可浏览广场内容，联系人/会话空态正常显示并可完成页面间导航。
- 连通性成功事件默认不上报；异常事件满足“每设备每 build 每 24 小时一次”。
- 连通性上报接口拒绝空设备请求；同去重指纹同日仅入库一次。
- 冷启动后账号分段与服务端一致，邀请能力显隐与分段一致。

## 实施状态

- 状态：已完成
- 最后更新：2026-04-30
- 实施结果：
  - 启动与登录入口已统一到 `preview-index`，未登录审核访问门控单一路由生效。
  - `preview-index` 与 `preview-profile` 已补齐通用样式导入，底部栏布局链路闭环。
  - Preview 数据层已提供最小广场可浏览数据，联系人/会话空态保持可用。
  - 连通性上报已实现“默认仅异常上报 + 客户端本地去重 + 服务端幂等去重与限频 + 空设备拒绝”。
  - `/user/profile` 已补充分段字段，冷启动分段同步链路已接入 `authService.initialize()`。
  - `square-demo` 页面与 `square-preview-data` 已迁移到 `deleted/review-preview-unification-20260430/`，主链路无并行分叉实现。
