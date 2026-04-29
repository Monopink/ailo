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

- `mini-program_captcha_provider`
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
- 兜底与降级的统一边界见 `docs/spec/error-handling.md`。

## 5) 配置域（config_scope）

`system_configs.config_scope` 用于区分配置治理边界：

- `system`：系统运行配置
- `security`：安全与风控配置
- `operation`：运营可调配置

运行时读取配置仍以 `config_key` 为唯一标识，`config_scope` 用于后台页面分域与权限隔离。

## 6) 配置分组（group_name）

`system_configs.group_name` 用于管理端设置页的展示分组；运行时读取配置仍以 `config_key` 为唯一标识。

### 分组语义

- 分组以“业务领域 / 链路”为边界：同一条链路内经常一起调参、一起排障、一起验收的配置项归为同一组。
- 治理手段（如限流、锁定、验证码）通过 `config_key` 表达；`group_name` 保持为配置项的业务归属链路。
- 分组应稳定且可扩展：新增配置项时，按其所属链路选择既有分组；当出现新链路时新增分组。

### 命名约束

- `group_name` 使用 `lower_snake_case`。
- `group_name` 长度不超过 50 字符（与数据库字段长度一致）。
- `group_name` 不包含客户端前缀；多客户端差异通过 `config_key` 的 `{client}_` 前缀表达。

## 7) 值类型（value_type）

`system_configs.value_type` 定义单项值的数据类型：

- `1`：`STRING`
- `2`：`NUMBER`
- `3`：`BOOLEAN`
- `4`：`JSON`
- `5`：`ENUM`
- `6`：`TIME`（UTC ISO8601 字符串）

## 8) 值形态（config_shape）

`system_configs.config_shape` 定义配置整体形态：

- `1`：`SINGLE`（`config_value` 为单值）
- `2`：`ARRAY`（`config_value` 为数组）

当 `config_shape=2` 时：

- `config_value` 为非空数组
- `default_value` 为标量参考值（可为空字符串）
