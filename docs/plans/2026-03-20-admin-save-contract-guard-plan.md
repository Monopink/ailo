# 2026-03-20 管理后台保存时校验防误操作方案

## 已确认决策

- 不在 Chat Console 页面增加状态展示。
- 不做按钮级限制，只在保存时执行校验。
- 本次仅覆盖以下链路，不扩展到其他入口：
  - `ai_template/create`
  - `ai_template/edit`
  - `ai_instance/create`
  - `ai_instance/edit`
  - `ai_style/advanced-edit` 保存
  - `ai_personality/advanced-edit` 保存

## 目标范围

- 将误操作防护统一收敛到“保存时校验”。
- 在保存提交时阻断不满足约束的数据写入。
- 不改动页面交互流程，不新增前置按钮禁用逻辑。

## 校验规则定义

### 1. Template/Instance 保存契约校验

- 适用链路：
  - `ai_template/create`
  - `ai_template/edit`
  - `ai_instance/create`
  - `ai_instance/edit`
- 校验内容：
  - `style` 的 dimension 名称集合与 `personality.json_schema.properties.score.properties` 字段名称集合完全一致。
- 不满足时：
  - 返回保存失败，不写入数据。
  - 错误信息包含 `missing_in_schema` 和 `extra_in_schema` 细节。

### 2. Style Advanced Edit 保存引用保护

- 适用链路：`ai_style/advanced-edit` 保存接口。
- 引用判定：
  - 存在任意 `ai_instances.style_id = 当前style_id` 或任意 `ai_templates.style_id = 当前style_id` 记录，视为“被引用”。
- 被引用时限制：
  - 禁止 dimension 集合变更（新增 dimension、移除 dimension）。
- 被引用时允许：
  - 不改变 dimension 集合前提下的其他保存内容（如显示信息、映射信息）可继续保存。
- 不满足时：
  - 返回保存失败，不写入 dimension 集合变更。

### 3. Personality Advanced Edit 保存引用保护

- 适用链路：`ai_personality/advanced-edit` 保存接口。
- 引用判定：
  - 存在任意 `ai_instances.personality_id = 当前personality_id` 或任意 `ai_templates.personality_id = 当前personality_id` 记录，视为“被引用”。
- 被引用时限制：
  - 禁止 `score` 维度名称集合变更（新增、移除、改名）。
  - “从 Style 获取 Dimension”导致集合变化时，保存必须失败。
- 被引用时允许：
  - 不改变 `score` 维度名称集合前提下的其他字段保存。
- 不满足时：
  - 返回保存失败，不写入集合变更。

## 实施任务

1. 复核并统一 `template/instance` 保存链路的契约校验行为与错误文案格式。
2. 在 `ai_style/advanced-edit` 保存接口增加“引用存在 + 集合变更”阻断校验。
3. 在 `ai_personality/advanced-edit` 保存接口增加“引用存在 + score 维度集合变更”阻断校验。
4. 为以上保存失败场景补充明确错误返回，确保页面可直接展示失败原因。
5. 补充后端测试用例，覆盖成功路径与阻断路径。

## 验收标准

- 在 `template/instance` 的 create/edit 中，style/personality 维度不匹配时，保存失败且无数据写入。
- 在 `ai_style/advanced-edit` 中，当 style 已被 instance/template 引用时：
  - 尝试新增或移除 dimension，保存失败。
  - 不变更 dimension 集合的保存请求，按原规则执行。
- 在 `ai_personality/advanced-edit` 中，当 personality 已被 instance/template 引用时：
  - 尝试变更 `score` 维度集合，保存失败。
  - 不变更 `score` 维度集合的保存请求，按原规则执行。
- 本次不新增 Chat Console 相关改动。
