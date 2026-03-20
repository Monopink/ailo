# 2026-03-20 AI Username 单一真相源重构方案

## 已确认决策

- `ai_personas.username` 为 AI username 唯一真相源。
- 删除 `ai_instances.username` 列（不再作为运行态冗余字段）。
- 引入 `ai_instances.persona_id`（可空）作为实例到 persona 的显式关联；手动实例 `persona_id` 为 `NULL`。
- `ai_instances.qiao_id` 保留，继续作为外部联系人标识字段使用。
- 移除 `username_consistency_status` 及其完整检测链路。
- Chat Console 保留 username 展示字段：来源统一为 persona.username；手动实例展示为空，不计入异常。
- 数据迁移采用严格失败策略：发现不一致数据即中止迁移并输出问题清单。
- 允许管理端修改 persona.username。

## 问题点

- 当前同时存在 `ai_personas.username` 与 `ai_instances.username`，属于冗余且存在一致性风险。
- 现有一致性约束与实现链路不完整，无法保证“persona 改名后所有关联实例字段同步更新”。
- 管理端 Chat Console 存在 username 对账语义字段，依赖冗余字段，增加实现复杂度与排障噪音。

## 需求点

- 系统内 username 的权威来源必须唯一，且不允许出现“静默不同步”的数据状态。
- 手动实例（`creation_metadata.source=admin_manual`）不绑定 persona，username 展示允许为空。
- 联系人、消息、会话等链路对 `qiao_id` 的既有语义与行为保持不变。

## 方案定义

### 1. 数据模型

- `ai_instances`：
  - 新增 `persona_id BIGINT NULL`，外键指向 `ai_personas.id`。
  - 删除 `username VARCHAR(20)`。
  - 删除与 instance.username 相关的索引与注释（例如基于 username 的索引）。
- `ai_personas`：
  - `username` 继续为对外 AI username 主数据。

### 2. 写入语义

- `creation_metadata.source=persona` 的实例创建：
  - 写入 `ai_instances.persona_id = ai_personas.id`。
  - 不写入 instance.username（字段已删除）。
- `creation_metadata.source=admin_manual` 的实例创建：
  - 写入 `ai_instances.persona_id = NULL`。

### 3. 读取语义

- 任何需要展示 AI username 的地方：
  - 当 `ai_instances.persona_id IS NOT NULL`：通过 persona 读取 `ai_personas.username`。
  - 当 `ai_instances.persona_id IS NULL`：username 返回空值。
- 禁止从 `ai_instances` 读取 username（字段不存在）。

### 4. 管理端 Chat Console 与 Debug API

- 移除字段与链路：
  - `username_consistency_status`
  - `persona_username`
  - `instance_username`
  - 相关的 mismatch/not_applicable 高亮与跳转提示逻辑
- 保留 `contact_username` 展示字段，但来源改为 persona.username 或空值。

## 实施步骤

1. 文档同步（先行）
- 更新下列文档，移除冗余与对账语义，并将 username 展示语义切换为 persona 单一真相源：
  - `docs/spec/ai/instance-lifecycle.md`
  - `docs/spec/contact/ai-creation.md`
  - `docs/spec/admin-panel/chat-console.md`
  - `docs/api/admin-debug-chat-console.md`
  - `docs/data-dict/ai-instantiation.md`

2. 数据库变更
- Alembic migration：
  - `ai_instances` 新增 `persona_id`（NULLable）。
  - `ai_instances` 删除 `username`。
  - 增加 `persona_id -> ai_personas.id` 外键。
  - 添加必要索引（例如 `ai_instances(persona_id)`）。
- 初始化脚本同步：
  - 同步更新 `backend/database/init/sql/01_schema.sql` 与数据字典。

3. 数据回填与严格失败校验
- 回填逻辑：
  - 对 `creation_metadata.source=persona` 的实例：用 `creation_metadata.persona_id` 回填 `ai_instances.persona_id`。
  - 对 `creation_metadata.source=admin_manual` 的实例：保持 `ai_instances.persona_id = NULL`。
- 严格失败校验（迁移过程中执行）：
  - `source=persona` 但缺失 `creation_metadata.persona_id`。
  - `source=persona` 但 `creation_metadata.persona_id` 指向 persona 不存在。
  - `source=persona` 但 `ai_instances.qiao_id <> ai_personas.qiao_id`（通过 persona_id join 后校验）。

4. 后端代码调整
- Model/Schema：
  - `AIInstance` 增加 `persona_id`，删除 `username`。
  - 更新涉及 instance.username 的 schema 与响应体结构。
- Service/Query：
  - 实例创建流程写入 persona_id。
  - 需要 username 的返回改为 join persona 读取。
- Admin：
  - Debug API 与 Chat Console 数据聚合结构同步移除对账字段。

5. 管理端前端调整
- Chat Console 页面移除一致性状态展示与高亮逻辑。
- `contact_username` 展示改为 persona.username 或空值。

## 验收标准

- 数据库中不存在 `ai_instances.username` 列。
- 数据库中存在 `ai_instances.persona_id`，且外键有效。
- 管理端与接口层不再出现 `username_consistency_status`、`persona_username`、`instance_username`。
- Chat Console 的 username 展示仅来自 persona.username 或为空；手动实例不触发异常提示。
- 迁移脚本在异常历史数据下严格失败，不发生静默修复、隐式回退或部分成功提交。
