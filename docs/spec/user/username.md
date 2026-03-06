# Username Rules

本文档定义 username 的服务端约束与判定规则。客户端可做同规则校验，但以服务端判定为准。

## 字段属性

- 表：`users`
- 字段：`users.username`
- 允许为 NULL；但只要提供值，就必须满足以下规则。
- 用户端通过 `PUT /api/v1/user/profile` 首次设置成功后不可修改。
- 管理端仅 `super_admin`、`admin` 可修改。

## 约束分层（单一规则源）

- 应用层（唯一规则源）：负责完整校验（格式、保留字）。
- 数据库层（保底约束）：只负责 NULL/长度/唯一，不重复实现复杂正则。
- 当应用层规则升级时，优先更新本文件与服务端实现，避免多处规则漂移。

## 格式规则

- 长度：5~20
- 字符集：仅允许字母、数字、`_`、`-`
- 首字符：必须是字母

正则（等价表达）：

```txt
^[A-Za-z][A-Za-z0-9_-]{4,19}$
```

## 唯一性规则（大小写不敏感）

- 唯一性按小写判定（case-insensitive unique）。
- 数据库存储保留用户输入的原始大小写。

判定逻辑：

```txt
LOWER(username) 全局唯一
```

## 可变性规则

- `users.username IS NULL` 时，用户端可提交 `username` 完成首次设置。
- `users.username IS NOT NULL` 时，用户端提交 `username` 必须拒绝。
- 已设置后，客户端资料页隐藏“编辑敲敲号”入口，仅展示当前值。

## 保留字规则

- 保留字禁止使用。
- 保留字配置项：`system_configs.username_reserved_words`
  - 类型：JSON 数组
  - 约束：配置内容必须为全小写
- 判定方式：将输入 username 转为小写后与保留字列表比较。

## 频控配置

- `system_configs.username_check_rate_limit_short_requests`：短窗口校验次数上限（默认 5）
- `system_configs.username_check_rate_limit_short_window_seconds`：短窗口秒数（默认 10）
- `system_configs.username_check_rate_limit_long_requests`：长窗口校验次数上限（默认 20）
- `system_configs.username_check_rate_limit_long_window_seconds`：长窗口秒数（默认 60）
- `system_configs.username_submit_rate_limit_requests`：提交次数上限（默认 3）
- `system_configs.username_submit_rate_limit_window_seconds`：提交窗口秒数（默认 60）
