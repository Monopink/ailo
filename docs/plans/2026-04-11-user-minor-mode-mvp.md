# 用户端：青少年模式最小实现（MVP）

## 目标

- 新增青少年模式能力，支持开启、关闭、修改密码。
- 后端仅记录状态与密码，不实现时段/功能限制判断。
- 客户端实现 `22:00-06:00` 发现功能本地禁用。

## 需求点

- 接口采用新增专用路径，不复用 `PUT /api/v1/user/settings`。
- 关闭青少年模式时必须密码校验。
- 密码仅存储哈希，禁止明文存储与返回。

## 问题点

- 当前项目文档存在 `GET/PUT /api/v1/user/settings` 描述，但代码侧未见对应用户设置路由实现。
- 仅做客户端本地时段限制可被绕过（改系统时间、抓包、旧客户端）。
- 不建设独立审计系统时，问题追溯能力受限。

## 接口方案

1. `GET /api/v1/user/minor-mode`
- 用途：读取当前账号青少年模式状态。
- 返回：`enabled`、`has_pin`、`enabled_at`、`pin_updated_at`。

2. `PUT /api/v1/user/minor-mode/enable`
- 用途：开启青少年模式并设置密码。
- 请求：`pin`（必填）。
- 行为：写入 `enabled=true`，写入 `pin_hash`，更新 `enabled_at/pin_updated_at`。

3. `PUT /api/v1/user/minor-mode/disable`
- 用途：关闭青少年模式。
- 请求：`pin`（必填）。
- 行为：校验通过后写入 `enabled=false`，清空 `pin_hash`，更新 `disabled_at`。

4. `PUT /api/v1/user/minor-mode/pin`
- 用途：修改青少年模式密码。
- 请求：`old_pin`、`new_pin`（均必填）。
- 行为：校验旧密码后更新 `pin_hash` 与 `pin_updated_at`。

5. `POST /api/v1/user/minor-mode/pin/verify`（可选）
- 用途：客户端在敏感操作前进行密码预验证。
- 请求：`pin`（必填）。

## 数据方案

- 在用户设置承载表新增字段（按现有设置模型实际落位）：
  - `minor_mode_enabled`（boolean, not null, default false）
  - `minor_mode_pin_hash`（string, nullable）
  - `minor_mode_enabled_at`（timestamp, nullable）
  - `minor_mode_disabled_at`（timestamp, nullable）
  - `minor_mode_pin_updated_at`（timestamp, nullable）

## 客户端方案

- 设置页新增青少年模式入口与状态展示。
- 开启流程：输入密码 + 二次确认。
- 关闭流程：输入密码校验通过后关闭。
- 修改密码流程：旧密码校验 + 新密码二次输入。
- PIN 规则固定为 4 位数字。
- 密码失败次数限制仅客户端本地生效（不做后端限制）。
- 发现页在 `22:00-06:00` 执行本地禁用与提示文案。

## 日志方案

- 不新增独立审计表。
- 记录应用日志事件：
  - `minor_mode_enabled`
  - `minor_mode_disable_success`
  - `minor_mode_disable_failed`
  - `minor_mode_pin_changed`

## 实施步骤

1. 后端模型与 migration
- 补充设置表字段与 Alembic migration。

2. 后端 schema 与 API
- 新增 minor-mode 请求/响应 schema。
- 新增 minor-mode 路由与密码校验逻辑。
- 接入错误码（PIN 错误、参数错误、状态冲突）。

3. 前端页面与服务
- 新增青少年模式设置页。
- 接入 enable/disable/pin 接口。
- 增加发现页本地时段禁用逻辑。

4. 文档
- 更新 `docs/api/user.md`（新增 minor-mode 接口契约）。
- 如涉及规范变更，再更新对应 `docs/spec/*`。

## 验收标准

- 可成功开启青少年模式并设置密码。
- 关闭青少年模式必须密码正确，且关闭后密码被清空。
- 修改密码流程可用，旧密码错误会失败。
- 客户端 `22:00-06:00` 发现页不可用并展示提示。
- API 不返回任何明文密码或哈希值。

## 已知风险

- 本期不做后端时段限制，客户端本地时段限制存在可绕过风险。
- 本期不做后端密码失败次数限制，客户端本地限制存在可绕过风险。

## 已确认参数

- 密码规则：固定 4 位数字 PIN。
- 密码失败次数限制：启用，但仅客户端本地生效。
