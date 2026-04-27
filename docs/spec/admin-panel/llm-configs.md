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
