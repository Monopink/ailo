# 小程序 Review Mode 与可见性治理方案

生效日期：2026-04-29

## 目标

- 小程序首屏满足审核要求：review_mode 开启时未登录可浏览。
- 访问判定分流：可连服务器走服务端判定，不可连服务器走本地 36 小时离线判定。
- 用户审核身份与青少年开关解耦。
- Square 分类可见性按 `review_visibility_scope` 与 `minor_visible` 交集过滤。
- 邀请能力对审核账号后端硬拦截，前端同步隐藏入口。
- 增加连通性诊断上报，支持审核环境问题定位。

## 最终数据设计

### users

- 保留：`user_type`（`1=normal,2=official,3=virtual`）
- 保留：`minor_mode_enabled`（布尔）
- 新增：`review_scope`（`0=non_review,1=mp_weixin_review`，默认 `0`）
- 移除：`audience_type`

### square_categories

- 新增：`minor_visible`（布尔，默认 `false`）
- 新增：`review_visibility_scope`（默认 `1`）
  - `0=ALL_USERS`
  - `1=REGULAR_USERS`
  - `2=ALL_REVIEWERS`
  - `3=MP_WEIXIN_REVIEWERS`
- 移除：`visibility_scope`

### system_configs

- `review_mode_mp_weixin_enabled`
- `review_mode_mp_weixin_ends_at`
- `review_mode_mp_weixin_auto_disable_enabled`
- `value_type` 扩展包含 `TIME=6`

### 诊断数据表

- 新增：`client_connectivity_events`
- 用于记录小程序启动连通性诊断事件。

## 运行时规则

### 启动模式判定

1. 先请求 `GET /api/v1/client/health`。
2. 请求成功：
   - `review_mode_active=true` 且未登录 -> 进入 `public_preview`。
   - `review_mode_active=false` 且未登录 -> 跳转登录页。
3. 请求失败：
   - 若当前时间 <= `BUILD_INFO.builtAt + 36h` 且未登录 -> `network_fallback_preview`。
   - 否则未登录跳转登录页。
4. 已登录：
   - `review_scope=1` -> `member_restricted`。
   - 其他 -> `member_standard`。

### 分类可见性

- 先按 `review_visibility_scope` 过滤当前用户可见范围。
- 再按 `minor_mode_enabled` 叠加 `minor_visible=true` 过滤。
- 两者为交集关系。

### 邀请能力

- `review_scope=1`：邀请接口统一返回 403。
- 前端隐藏邀请入口与邀请页面跳转。

## 实施清单

1. 迁移脚本重构：`review_scope`、`minor_visible`、`review_visibility_scope`、诊断表。
2. 后端模型/枚举替换：移除 `audience_type` 与旧可见性枚举。
3. 后端业务替换：注册打标、发现页过滤、邀请拦截。
4. 新增客户端接口：`/client/health`、`/client/connectivity-events`。
5. 小程序启动改造：服务端判定 + 本地 36h 判定 + 诊断上报。
6. 小程序用户结构改造：`review_scope` 替代 `audience_type`。
7. 小程序 UI 修复：Profile 页仅隐藏邀请分组，不隐藏资料分组。
8. 下线 `pkg/square-demo` 路由入口，统一主链路预览。

## 验收标准

- review_mode 开启时，未登录可直接浏览广场。
- 服务端不可达且在构建后 36 小时内，未登录可进入离线预览。
- review_scope 审核账号看不到邀请能力，邀请接口后端返回 403。
- Square 分类严格按 `review_visibility_scope` 和 `minor_visible` 双条件过滤。
- 文档与接口字段统一为 `review_scope`。
