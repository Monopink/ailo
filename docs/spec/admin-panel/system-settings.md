# 系统设置规范

系统设置页与运营设置页负责 `system_configs` 管理。

## 配置管理

- 配置列表：
  - 系统设置页展示 `config_scope in {system, security}` 配置
  - 运营设置页展示 `config_scope = operation` 配置
  - 两个页面均按 `group_name` 动态分组展示
- 配置编辑：支持字符串、数字、布尔、JSON、枚举
- 快捷编辑：一键复制当前值到输入框后再修改
- 分组导航：右下角 `Quick Nav` 浮动按钮
- 配置历史：通过 `admin_operation_logs` 追踪

## 运营设置页（Operation Settings）

- 邀请奖励策略卡片：
  - 展示字段：`被邀请人奖励增量`、`邀请人奖励增量`、`邀请人奖励次数上限`
  - 读取接口：`GET /admin-api/system/invitation-policy`
  - 保存接口：`PUT /admin-api/system/invitation-policy`
- 角色行为：
  - `super_admin/admin`：可读取、可保存
  - `viewer`：可读取、可刷新、不可保存

## 配置值类型（`value_type`）

1. `STRING=1`：文本值
2. `NUMBER=2`：整数值
3. `BOOLEAN=3`：布尔值
4. `JSON=4`：JSON 值
5. `ENUM=5`：受限选项值（需配合 `allowed_values`）
6. `TIME=6`：UTC 时间字符串（ISO8601）

`TIME` 类型在管理后台的输入与回显规则：

- 输入控件：`field-datetime`（基于 flatpickr）
- 提交存储：转换为 UTC ISO8601 字符串（带 `Z`）
- 页面回显：UTC 值转换为管理员本地时区显示

## 配置形态（`config_shape`）

1. `SINGLE=1`：单值配置（`config_value` 为单值）
2. `ARRAY=2`：数组配置（`config_value` 为数组，`default_value` 为标量默认填充值，可为空字符串）
