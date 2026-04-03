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

### description 边界

- style 页面保存 `dimensions[].description` 时写入 `ai_dimensions.description`。
- 已存在 personality 的 `json_schema.properties.score.properties.<dimension>.description` 保持原值。

---

## score description 来源链路

- 运行时权威来源：personality `json_schema.properties.score.properties.<dimension>.description`。
- 默认来源：`ai_dimensions.description`。
- 当 personality schema 中该维度 description 缺失时，使用维度默认描述。
- style 页面修改默认描述后，personality schema 通过人格页字段级恢复默认显式采用新默认值。
