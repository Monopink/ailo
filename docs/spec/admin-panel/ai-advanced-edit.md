管理端 AI Advanced Edit 页面定义了 `ai_personality` 与 `ai_style` 的高级配置编辑行为。

---

## ai_personality Advanced Edit

### 页面职责

- 编辑 `prompt`。
- 编辑非分数字段（`score` 之外）`description`。
- 编辑 `score` 顶层字段（`score` 对象本身）的 `description`。
- 管理 custom fields 与 placeholders。
- 展示 `score` 维度信息与范围，不在本页编辑 `score` 维度描述。

### 字段分组

- 统一数据模型：`field_entries[]`。
- `field_entries.group = system_fixed`：系统固定字段，支持 description 编辑。
- `field_entries.group = score_root`：`score` 顶层字段，支持 description 编辑与按字段恢复默认。
- `field_entries.group = score_dimension`：只读分组，展示 `name/display_name/min/max/description/default_description`。
- `field_entries.group = system_preset | custom`：可编辑；`system_preset` 支持从预设添加与移除。

### description 编辑交互

- 统一采用单一字段编辑模态框（`FieldEditorModal`）处理 `system_fixed / score_root / system_preset / custom`。
- 模态框展示：
  - 当前 description；
  - 默认 description；
  - 按字段恢复默认操作。
- 按字段恢复默认仅作用于当前字段，并立即更新页面草稿态。

### placeholder 管理交互

- placeholder 采用列表行内编辑（Key/Display Name/Description/Example Value/Required），整页保存。
- `placeholder_key` 规则：必填；不可重复；仅允许 `[A-Za-z0-9_]+`；禁止以 `score:` 开头。
- 修改 `placeholder_key` 时：当提示词模板中已存在 `{{old_key}}`，弹出确认；用户确认后全量替换为 `{{new_key}}`。
- 删除 placeholder：弹窗必须展示被删除条目的 `placeholder_key`。
- “从提示词模板导入”：解析当前提示词模板中所有 `{{...}}`；对未知 placeholder 自动新增条目并填充 `placeholder_key`；不合法的 key 需提示并跳过。
- CSV 导出/导入：
  - 导出：复制为 CSV 文本（含表头：`placeholder_key,display_name,description,example_value,is_required`）。
  - 导入：粘贴 CSV → 解析预览 → 二次确认；若与当前已存在 key 重复则标记并提示将覆盖；确认后按 key 覆盖/新增。

### 预设字段来源

- “从预设添加”列表由后端配置聚合接口返回。
- 预设字段定义来源于后端 Schema 字段注册表。

### 保存规则

- 提交 `prompt`、`schema_config`、`placeholders` 为单事务。
- `score` 维度集合在 personality 被 instance/template 引用时保持锁定。
- `score` 顶层描述随 `schema_config.score_description` 写回 personality schema。
- `score` 维度描述随 `schema_config.dimensions[].description` 写回 personality schema。

---

## ai_style Advanced Edit

### 页面职责

- 编辑 style 与 dimension 关联。
- 编辑 `ai_dimensions.description` 作为维度默认描述来源。
- 编辑 mapping 与初始位置规则。
- “关联 Dimension”使用可搜索选择组件，从当前未关联维度中远程搜索并选择。

### description 边界

- style 页面保存 `dimensions[].description` 时写入 `ai_dimensions.description`。
- 已存在 personality 的 `json_schema.properties.score.properties.<dimension>.description` 保持原值。

---

## score description 来源链路

- 运行时权威来源：personality `json_schema.properties.score.properties.<dimension>.description`。
- 默认来源：`ai_dimensions.description`。
- 当 personality schema 中该维度 description 缺失时，使用维度默认描述。
- style 页面修改默认描述后，personality schema 通过人格页字段级恢复默认显式采用新默认值。
