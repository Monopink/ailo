# system_configs 命名约定

本规范用于约束 `system_configs.config_key` 的命名，避免歧义与重复配置。

## 1) 作用域前缀

- **用户侧**：默认不加 `user_` 前缀（即“无前缀”代表用户侧）。
- **管理员侧**：统一使用 `admin_` 前缀。

示例：

- 用户侧：`auth_password_max_failures`
- 管理员侧：`admin_auth_max_failures`

## 2) 客户端区分（多客户端）

当同一能力需要区分不同客户端（例如小程序/web/app），使用 `{client}_` 前缀区分：

- `{client}_xxx`

其中 `{client}` 的取值来源于请求侧约定（例如 HTTP Header `X-Client` 的值，统一小写）。

示例：

- `wxminipg_captcha_provider`
- `web_captcha_provider`

## 3) 时间单位

时间类配置必须把单位写入 key，避免误用：

- 秒：`*_seconds`
- 分钟：`*_minutes`
- 小时：`*_hours`
- 天：`*_days`

## 4) 避免“默认兜底”隐藏错误

当某个能力需要明确配置才能启用时：

- 服务端读取配置缺失应视为错误或明确“未启用”，不得悄悄回退到不可预期的行为。
