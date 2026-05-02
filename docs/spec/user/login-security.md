# 登录安全策略（Auth Login）

目标：在不引入向后兼容包袱的前提下，为登录链路提供统一安全约束，覆盖账号密码登录、微信登录、手机号登录三类签发 JWT 的入口。

---

## 适用范围

本策略覆盖会签发 JWT 的接口

---

## 核心原则

- 速率限制与失败锁定必须可配置（`system_configs`），且 key 语义清晰。
- Password Login 以 `client_ip + identifier_key` 作为主要防护维度。
- 所有登录接口必须强制 `device_id`（UUID），禁止无 `device_id` 登录路径。
- 禁止在日志/埋点/审计记录中记录 access_token/refresh_token（包括任何片段）。
- 失败提示避免泄露“账号是否存在”等敏感信息（统一失败文案）。
- 当前实现若为进程内缓存，多 worker/多实例部署时必须迁移为共享存储（例如 Redis）。

---

## 会话与审计约束

### Token Secret 边界

- `user_tokens` 是认证状态表，可保存认证所需会话字段。
- `login_records` 是审计表，禁止保存 token 明文或片段。

### JWT session_id 语义

- `JWT.session_id` 必须等于 `user_tokens.id`（稳定会话主键）。
- 刷新 access token 时，不得生成新的 `session_id`。

### login_records 记录策略

- 成功登录：记录 `user_token_id = user_tokens.id`。
- 失败登录：`user_token_id = NULL`。
- 审计追踪统一通过 `user_token_id` 完成，不通过 token 明文完成。

---

## Password Login 风控定义

### identifier_key

`identifier` 归一化后的键（用于风控聚合）：

- email：小写
- phone：规范化后（E.164）
- username：小写

### auth_identifier（锁定/限流维度）

`auth_identifier = "{client_ip}:{identifier_key}"`

---

## system_configs

### 速率限制（双窗口）

短窗口用于阻止瞬时爆发；长窗口用于阻止持续尝试。

- `auth_password_rate_limit_short_requests`（int，默认 5）
- `auth_password_rate_limit_short_window_seconds`（int，默认 10）
- `auth_password_rate_limit_long_requests`（int，默认 20）
- `auth_password_rate_limit_long_window_seconds`（int，默认 60）

### 失败锁定

- `auth_password_max_failures`（int，默认 5）
- `auth_password_failure_window_seconds`（int，默认 1800 / 30min）
- `auth_password_lockout_duration_seconds`（int，默认 900 / 15min）

语义：

- `failure_window`：统计失败次数的时间窗
- `lockout_duration`：触发锁定后的锁定时长

---

## Password Login 服务端行为

顺序：

1) 按 `CLIENT_IP_MODE` 解析并校验 `client_ip`
2) 构造 `auth_identifier`
3) 若处于 lockout：返回保护性拒绝同态（对外复用普通失败三元组：`HTTP 400` + `error_code` + `message=登录失败，请稍后再试`），真实原因仅写日志（含 `retry_after`）
4) 进行双窗口 rate limit：超限返回保护性拒绝同态（对外复用普通失败三元组：`HTTP 400` + `error_code` + `message=登录失败，请稍后再试`），真实原因仅写日志（含 `retry_after`）
5) 校验密码：
   - 凭证无效（账号不存在 / 密码错误）：记录一次 failure（计入 `failure_window`），返回 400 + `账号或密码错误`
   - 账号状态非 ACTIVE：记录一次 failure（计入 `failure_window`），返回 400 + `账号状态异常`
   - 成功：清空 failure 记录，继续签发 token

---

## 攻击检测与处罚闭环

本节适用于登录链路与统一 API 安全接入层。

### 检测分类

- `prompt_injection`
- `sql_injection`
- `command_injection`
- `path_traversal`
- `other`

### 独立处罚轨

- 用户处罚轨（仅在可定位账号时生效）：
  - 高危命中后将 `users.status` 更新为 `suspended`
  - 立即撤销该账号全部有效 `user_tokens`
  - 同步更新 `user_risk_stats`
- IP 处罚轨（与用户处罚独立）：
  - 所有命中先累计到 `security_ip_risk_stats`
  - 仅当窗口计数达到阈值后，写入 `security_ip_blocks` 执行 TTL 封禁

### 默认阈值与 TTL

- 高危窗口：5 分钟，阈值 `>= 8`
- 高危封禁 TTL：86400 秒（24 小时）
