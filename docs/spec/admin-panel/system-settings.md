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
- 运营设置页邀请策略卡片：
  - 读取与保存端点：`GET /admin-api/system/invitation-policy`、`PUT /admin-api/system/invitation-policy`
  - 编辑字段：
    - `invitee_reward_contact_delta`
    - `inviter_reward_contact_delta`
    - `inviter_max_rewards_per_actor`
  - 邀请分享文案配置项：
    - `operation_invite_share_command_texts`
    - `operation_invite_share_card_titles`
  - 邀请分享文案仅在通用配置列表编辑，邀请策略卡片仅用于奖励规则参数
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

## LLM 配置规则

### 多配置管理

- 同一个 Provider（如 `doubao`）允许存在多条配置
- 通过 `display_name` 区分不同用途（如 Production/Test/Backup）
- `name` 用于代码层 SDK 选择，`display_name` 用于 UI 唯一展示

### `json_schema_mode` 规则

- 新配置默认 `auto`（未验证）
- 在配置测试页完成测试后自动更新：
  - 返回 JSON：更新为 `strict`
  - 返回普通文本：更新为 `disabled`
- AI Instance 功能只允许使用 `strict`
- 运行时保护：
  - `auto`：提示“未验证，请先测试”
  - `disabled`：提示“不支持 JSON Schema，无法使用”
  - `strict` 若返回非 JSON：自动降为 `disabled` 并报错

### API Key 管理

- API Key 不入库，仅存环境变量
- `api_key_env` 指定环境变量名（如 `DOUBAO_PROD_API_KEY`）
- `api_key_env` 为空时按默认命名：`{NAME}_API_KEY`
