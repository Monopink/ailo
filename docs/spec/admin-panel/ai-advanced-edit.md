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
- 全局唯一 key 的真相源为 `system_configs.ai_global_unique_placeholder_keys`（字符串数组）。
- Placeholder 卡片支持“从全局唯一导入”：打开多选弹窗，候选项来自 `system_configs.ai_global_unique_placeholder_keys`；确认后按 `placeholder_key` 导入（已存在 key 跳过），导入默认 `is_required=true`。
- Placeholder 列表对命中 `system_configs.ai_global_unique_placeholder_keys` 的 key 显示只读标注（Global Unique），不提供逐条开关。
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
- `placeholder_key` 在同一 personality 范围内唯一。
- `score` 维度集合在 personality 被 instance/template 引用时保持锁定。
- `score` 顶层描述随 `schema_config.score_description` 写回 personality schema。
- `score` 维度描述随 `schema_config.dimensions[].description` 写回 personality schema。

---

## ai_instance Advanced Edit

### 页面职责

- 编辑 `prompt_variables`。
- 编辑 `dimensions` 与位置映射配置。
- 编辑 `status`（仅允许 `ACTIVE/INACTIVE`，字段位于页面可编辑字段列表末尾）。
- 管理实例记忆（`ai_instance_memories`）。

### 保存规则

- 提交 `prompt_variables`、`dimensions`、`positions`、`relationship_id`、`status`、`memory_changes` 为单事务。
- `BLOCKED(3)` 属于系统态，不提供人工直接设置入口。

---

## ai_template Advanced Edit

### 页面职责

- 编辑 `status`（仅允许 `ACTIVE/INACTIVE`）。
- 编辑 `prompt_variables`。
- 编辑 `position_mapping_config`。
- 管理模板记忆（`ai_template_memories`）。

### 保存规则

- 提交 `status`、`prompt_variables`、`position_mapping_config`、`memory_changes` 为单事务。
- `USED(3)` 属于系统态，不提供人工直接设置入口。
- 仅当发生 `非 ACTIVE -> ACTIVE` 状态切换时，触发激活前校验：
  - Personality 的必填 placeholders 必须在 `prompt_variables` 中具备非空值；
  - 若缺失任一必填项，保存被拒绝。
- 保存时对 `system_configs.ai_global_unique_placeholder_keys` 执行全局同值检查（仅检查当前 template 所属 personality 已定义的同名 key）：
  - 检查范围为全部 templates；
  - 仅检查非空值；
  - 归一化规则为 `trim` 与换行统一（`\r\n` → `\n`）后精确比较；
  - 当配置结构异常（非字符串数组或数组内含非字符串项）时，跳过全局唯一检查并在保存成功后提示管理员检查配置；
  - 命中冲突时返回可确认冲突，不做硬阻断。
- 管理员可在冲突确认弹窗中选择继续或取消：
  - 继续：携带 `force_continue=true` 重新提交并保存；
  - 继续保存会写入管理员操作审计日志（含冲突明细）；
  - 取消：留在当前页继续编辑，不写入数据。

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
