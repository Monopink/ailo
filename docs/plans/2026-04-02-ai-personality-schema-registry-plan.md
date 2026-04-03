# 2026-04-02 ai_personality advanced-edit JSON Schema 配置重构方案（代码注册表）

## 已确认决策

- 预设字段能力采用代码注册表架构，不新增数据库表。
- 不使用 `system_configs` 承载预设字段定义。
- `ai_personality/advanced-edit` 仅允许编辑非分数字段的 `description`。
- 非分数字段采用“编辑按钮 -> 模态框”交互；模态框提供“按字段恢复默认”能力，并展示默认值。
- `score` 顶层字段（`score` 对象本身）description 在 `ai_personality/advanced-edit` 可编辑并支持按字段恢复默认。
- `score` 维度字段（`score.<dimension>`）在 `ai_personality/advanced-edit` 只读展示。
- `score` 维度 `description` 的运行时权威来源是 personality `json_schema`。
- `ai_dimensions.description` 作为 `score` 维度默认来源。
- `ai_style/advanced-edit` 修改 `ai_dimensions.description` 后，不自动同步已存在 personality schema。

## 问题点

- 页面字段描述渲染依赖 `INITIAL_SCHEMA` 初始快照，未绑定当前编辑态，导致显示值与保存值不一致。
- 分数字段描述在 UI 层存在 `N/A` 误导展示路径。
- 非分数字段默认描述与预设字段定义散落在前端和后端，存在漂移风险。
- 当前高级编辑初始化依赖多次拼装请求，缺少统一聚合契约。

## 目标范围

- 重构 `ai_personality/advanced-edit` 的字段描述编辑、展示、保存链路。
- 支持管理员编辑所有非分数字段 `description`，包括系统固定字段和系统预设字段。
- 支持在字段编辑模态框中执行“按字段恢复默认”。
- 保持 `score` 维度名称集合引用保护规则不变。
- 保持 `score` 维度 `description` 以 personality schema 为权威，在人格高级编辑页只读展示。

## 架构方案

### 1. Schema 字段注册表（后端单一来源）

- 新增后端 Schema 字段注册表模块，统一定义系统固定字段与系统预设字段元数据：
  - `field_name`
  - `type`
  - `default_description`
  - `default_required`
  - `category`（`system_fixed` / `system_preset`）
  - `editable_description`
  - `restorable`
- `current_state`、`internal_thoughts` 由注册表下发默认定义。
- `generate_json_schema`、高级编辑聚合接口、保存校验共同使用注册表。

### 2. 高级编辑聚合接口

- 新增接口：`GET /admin-api/ai/ai-personality/{personality_id}/advanced-config`。
- 响应一次性返回：
  - personality 基础信息（`id/display_name/prompt/status`）；
  - `score` 维度列表（`name/display_name/min/max/description/default_description/is_default`），只读；
  - 非分数字段列表（当前描述、默认描述、是否可编辑、是否可恢复）；
  - 当前 custom fields；
  - 可用预设字段列表（来源于后端注册表）；
  - 保存约束（是否被引用、`score` 集合是否受限）。
- 前端统一使用该接口初始化 `baseline + draft`，不再依赖 `INITIAL_SCHEMA` 展示。

### 3. 前端交互与状态模型

- 建立 `baseline + draft + dirty` 三态模型，所有表格渲染读取 `draft`。
- 非分数字段行提供“编辑”按钮，点击后打开模态框：
  - 展示当前值；
  - 展示默认值；
  - 支持“恢复默认”写回当前字段草稿值。
- 分数字段行保留只读展示，不提供编辑入口。
- `score` 顶层字段行提供编辑按钮，使用模态框编辑与按字段恢复默认。
- “从预设添加”弹窗改为后端聚合接口返回，不保留前端硬编码列表。

### 4. description 权威与归一化规则

- `score` 维度：
  - 优先读取 `json_schema.properties.score.properties.<name>.description`；
  - 当 personality schema 中该维度描述缺失时，以 `ai_dimensions.description` 作为默认显示值；
  - 保存时将当前 `draft` 中的维度描述写回 personality schema，保持 personality schema 权威来源。
- 非分数字段：
  - 当前描述来自 personality schema（或该字段当前配置）；
  - 默认描述来自注册表；
  - 恢复默认将字段描述重置为注册表默认值。

### 5. 保存链路与约束

- `POST /admin-api/ai/ai-personality/{personality_id}/save` 保持单事务语义。
- 继续保留并前置执行引用保护校验：
  - 被引用时禁止变更 `score` 维度名称集合；
  - 被引用时允许 `score` 同名集合下属性变更（`min/max/description`）。
- 新增非分数字段描述提交与校验：
  - 系统固定字段仅允许提交 `description` 覆盖；
  - 系统预设字段保持类型约束，允许 `description/required` 按页面提交值保存；
  - custom field 保持现有校验规则。

### 6. 与 ai_style 的边界

- `ai_style/advanced-edit` 修改 `ai_dimensions.description` 仅更新维度默认值来源。
- 已存在 personality schema 的 `score` 维度描述不自动同步。
- personality 页面通过“按字段恢复默认”显式采用最新默认值。

## 实施任务

1. 新增 Schema 字段注册表模块，收敛系统固定字段与系统预设字段默认定义。
2. 新增 `advanced-config` 聚合接口，输出高级编辑初始化所需完整结构。
3. 重构 `ai_personality_advanced_edit.html` 状态模型，移除 `INITIAL_SCHEMA` 展示依赖。
4. 为所有非分数字段添加“编辑按钮 -> 模态框”描述编辑交互。
5. 在字段编辑模态框中增加“按字段恢复默认”，并展示默认值。
6. 将“从预设添加”数据源切换为后端聚合返回，删除前端硬编码预设列表。
7. 对齐保存接口校验与 schema 生成逻辑，保证注册表与保存规则一致。
8. 更新 `docs/api/admin-ai-personality-advanced-edit.md` 与 `docs/api/admin-ai-style-advanced-edit.md`。
9. 补充接口、页面与回归验证用例。

## 验收标准

- 非分数字段 `description` 支持模态框编辑、保存、刷新回显。
- 字段编辑模态框展示默认值，并可按字段恢复默认后保存生效。
- 分数字段在 personality 页面只读展示，不提供编辑入口。
- 页面不再出现由初始快照导致的 `score description = N/A` 误导展示。
- 预设字段列表由后端返回，前端不含预设硬编码。
- `score` 维度描述运行时以 personality schema 为权威；缺失时展示维度默认描述。
- `ai_style` 修改维度描述后，不自动改写已存在 personality schema。

## 验证清单

- 接口验证：
  - `GET advanced-config` 返回结构完整，包含字段默认值与可恢复标记。
  - `POST save` 在字段描述编辑、按字段恢复默认、预设添加、引用保护场景下行为符合契约。
- 页面验证：
  - 非分数字段编辑后表格即时更新；
  - 按字段恢复默认后即时更新并可正确保存；
  - 分数字段显示链路不再出现 `N/A` 误导；
  - 未保存离开提示与保存后脏状态清理正常。
- 回归验证：
  - placeholder 管理不受本次改造影响；
  - Prompt 中 `score:<dimension>` placeholder 校验逻辑不受影响。

## 非本次范围

- 不新增预设数据库表。
- 不引入 `system_configs` 动态管理预设。
- 不新增“全部恢复默认”能力。
- 不变更 relationship score 计算算法与运行时消息处理流程。
