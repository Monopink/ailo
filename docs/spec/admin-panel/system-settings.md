# 系统设置规范

系统设置页与运营设置页负责 `system_configs` 管理。

## 系统状态卡片

页面顶部展示系统状态卡片，状态定义与仪表盘保持一致。

参考：[dashboard.md](dashboard.md#系统状态卡片)

## 系统对话管理

### 展示内容

- 当前系统对话 ID
- 创建时间
- Webhook URL（包含 token）
- 警告提示

### 操作按钮

- `[重新初始化系统对话]`
- `[重新生成 Webhook Token]`
- `[复制 Webhook URL]`

## 配置管理

- 配置列表：
  - 系统设置页展示 `config_scope in {system, security}` 配置
  - 运营设置页展示 `config_scope = operation` 配置
  - 两个页面均按 `group_name` 动态分组展示
- 配置编辑：支持字符串、数字、布尔、JSON、枚举
- 快捷编辑：一键复制当前值到输入框后再修改
- 分组导航：右下角 `Quick Nav` 浮动按钮
- 配置历史：通过 `admin_operation_logs` 追踪

## 配置值类型（`value_type`）

1. `STRING=1`：文本值
2. `NUMBER=2`：整数值
3. `BOOLEAN=3`：布尔值
4. `JSON=4`：JSON 值
5. `ENUM=5`：受限选项值（需配合 `allowed_values`）

## 配置形态（`config_shape`）

1. `SINGLE=1`：单值配置（`config_value` 为单值）
2. `ARRAY=2`：数组配置（`config_value` 为数组，`default_value` 为标量默认填充值，可为空字符串）
