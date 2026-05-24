## 文档目的

定义 `ai_template` 高级编辑中“全局唯一 Prompt Variables 软冲突确认”能力的当前实施方案：真相源改为 `system_configs`，并移除 personality 级配置链路。

## 目标

- 完整移除 personality placeholder 的 `is_global_unique` 配置能力。
- 以 `system_configs.ai_global_unique_placeholder_keys` 作为全局唯一 key 列表真相源。
- `ai_template` 高级编辑保存时，按全局配置执行冲突检查，命中冲突后二次确认，不做硬阻断。
- `ai_personality` 高级编辑 placeholder 卡片支持“从全局唯一导入（多选）”与只读标注显示。

## 固化决策

- 真相源配置项：
  - `config_key`: `ai_global_unique_placeholder_keys`
  - `value_type`: `STRING`
  - `config_shape`: `ARRAY`
  - `config_scope`: `operation`
  - `group_name`: `operation`
  - `config_value` 默认值：`["name"]`
  - `default_value` 预设项：`"name"`
- 唯一性范围：全库全部 templates（`ACTIVE`、`INACTIVE`、`USED`）。
- 比较口径：`trim` + 换行归一化（`\r\n` -> `\n`）后精确匹配。
- 空值规则：空字符串不参与冲突检查。
- 关闭规则：`ai_global_unique_placeholder_keys=[]` 视为关闭全局唯一检查。
- 冲突响应：首次提交命中冲突返回 `409` + `requires_confirmation=true` + 冲突模板信息。
- 二次提交：前端带 `force_continue=true` 重新提交并保存。
- personality 导入规则：从全局唯一列表多选导入；已存在 key 跳过；导入默认 `is_required=true`。
- 迁移策略：开发环境数据不保留；迁移链允许清理并重放，最终仅保留当前有效方案。

## 变更范围

- 数据库迁移与模型：
  - `backend/alembic/versions/*.py`
  - `backend/app/models/ai/personality.py`
  - `backend/database/init/02_required_data.sql`
- 管理端 API：
  - `backend/app/api/admin/ai_template.py`
  - `backend/app/api/admin/ai_personality.py`
  - `backend/app/services/system_config.py`（补充空数组可用的读取语义）
- 管理端高级编辑前端：
  - `backend/app/admin/templates/custom_views/ai_personality_advanced_edit.html`
  - `backend/app/admin/static/js/advanced-edit/pages/personality*.js`
  - `backend/app/admin/templates/custom_views/ai_template_advanced_edit.html`
  - `backend/app/admin/static/js/advanced-edit/pages/template.js`
- 文档：
  - `docs/spec/admin-panel/ai-advanced-edit.md`
  - `docs/api/admin-ai-template-advanced-edit.md`
  - `docs/api/admin-ai-personality-advanced-edit.md`

## 实施步骤

1. 清理 migration 链并重放开发环境数据库（不保留旧数据）。
2. 删除 personality placeholder 的 `is_global_unique` 列与前后端读写链路。
3. 新增 `system_configs.ai_global_unique_placeholder_keys` 并纳入系统设置页管理。
4. 修改 template 保存冲突检查逻辑为读取 `system_configs` 列表。
5. 在 personality placeholder 卡片新增“从全局唯一导入（多选）”与只读标注渲染。
6. 更新 CSV 导入导出：移除 `is_global_unique` 列与相关校验。
7. 完成联调、自测与文档验收。

## 验收标准

- personality 高级编辑请求/响应不再包含 `is_global_unique` 字段。
- CSV 表头更新为 `placeholder_key,display_name,description,example_value,is_required`。
- template 高级编辑保存时：
  - 命中激活必填缺失仍返回 `400`；
  - 命中全局唯一冲突且 `force_continue=false` 返回 `409`；
  - 命中全局唯一冲突且 `force_continue=true` 保存成功。
- `ai_global_unique_placeholder_keys=[]` 时，保存不触发全局唯一冲突检查。
- Personality 卡片可从全局唯一列表多选导入，且命中 key 显示只读标注。
- `docs/spec/*` 与 `docs/api/*` 契约与实现一致。

## 当前状态

- 状态：规划中（2026-05-24）。
