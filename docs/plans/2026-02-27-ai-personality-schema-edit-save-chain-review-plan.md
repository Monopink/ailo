# AI Personality Advanced Edit 编辑保存链路修订方案

## 1. 本次边界

- 管理员交互范围限定为 ai_personality_advanced_edit 增加 score_min/score_max 配置能力。
- AI 对话主流程不变，响应处理顺序不变，关系算法不变。
- style 与 personality 的自由组合关系不变。
- current_state/internal_thoughts 按管理员可选字段落地，不作为固定系统字段。
- 本次改动只包含安全校验、契约校验、事务一致性与代码重构。
- 不处理当前数据库历史数据修复；仅修正 init SQL 脚本中的不合规数据（如存在）。
- 运行时遇到契约不合规配置直接报错，不使用回退值。

## 2. 设计前提（契约模型）

- dimension 是契约。
- style 定义契约维度集合（参与打分的维度名）。
- personality 在 JSON Schema 的 score 字段下定义每个维度的 minimum/maximum。
- style 与 personality 只有在契约匹配时可组合工作。

## 3. 当前链路与偏差

1. ai_personality_advanced_edit 页面构造 schema_config（dimensions/custom_fields）。
2. 保存接口基于 schema_config 生成并保存 personality.json_schema。
3. 关系预览链路从 personality.json_schema 读取 score minimum/maximum。
4. 运行时 build_response_schema(context) 按 style 维度动态构建，当前实现存在固定 0..1000 路径。

偏差点：

- 预览与运行时对 score 范围的来源不一致。
- advanced-edit 页面展示字段契约与 response_schema.py 标准结构不一致。
- 保存链路存在非原子提交、跨人格占位符越权更新/删除、前端 innerHTML 渲染风险。

## 4. 目标状态

### 4.1 Schema 契约统一

- 保持 personality.json_schema 为 score minimum/maximum 的唯一存储载体。
- build_response_schema 产物与 personality.json_schema 契约一致。
- 运行时和预览使用同一份契约语义：score 维度集合来自 style，score 范围来自 personality schema。

### 4.2 管理页面契约对齐

- ai_personality_advanced_edit 的字段结构与 response_schema.py 完全对齐。
- memory_operations 固定为 object 结构。
- should_block 保持非必填。
- current_state/internal_thoughts 作为可选字段，由管理员决定是否加入和是否 required。

### 4.3 保存安全与一致性

- personality 保存在单事务内完成 prompt/json_schema/placeholders 全部更新。
- 更新和删除 placeholder 时强制校验 personality_id 归属。
- 自定义字段名冲突、required 重复、非法 type、score 维度缺失范围等在保存时直接拒绝。
- 前端可编辑内容渲染不使用 innerHTML 拼接。

### 4.4 组合契约校验前置

- 在 personality 保存时校验 schema 格式合法性。
- 在 template 绑定 style + personality 时校验契约匹配：
  - style 维度集合与 personality.score.properties 一致；
  - 每个维度 minimum/maximum 存在且合法。
- 校验失败时拒绝保存。

## 5. 实施内容

1. 对齐 ai_personality_advanced_edit 的 schema 字段定义与展示结构。
2. 扩展页面对 score_min/score_max 的配置与校验。
3. 重构 ai_personality 保存接口为单事务写入。
4. 增加 placeholder 归属校验与输入合法性校验。
5. 收敛 build_response_schema 与关系预览的 score 范围来源。
6. 在 template 绑定链路增加 style/personality 契约校验。
7. 修正 init SQL 中不合规样例数据（若存在）。
8. 同步文档：spec/data-dict/api 与实现一致。

## 6. 验收标准

- ai_personality_advanced_edit 可配置并保存 score_min/score_max。
- 当前对话主流程行为与处理顺序保持不变。
- 同一 style + personality 组合在预览与运行时使用一致的 score 范围。
- personality 保存接口在任意失败场景不产生部分提交。
- placeholder 无法跨 personality 更新或删除。
- 管理页面对可编辑文本无存储型 XSS。
- template 绑定在契约不匹配时被拒绝。
- 运行时遇到不合规契约配置直接报错。
- init SQL 中 personality/schema 样例数据满足契约规则。

## 7. 涉及文件

- backend/app/admin/templates/custom_views/ai_personality_advanced_edit.html
- backend/app/api/admin/ai_personality.py
- backend/app/services/ai/response_schema.py
- backend/app/services/ai/relationship_scoring.py
- backend/app/services/ai/orchestrators/conversation_flow.py
- backend/app/services/admin/instance_relationship.py
- backend/app/api/admin/ai_template.py
- backend/app/admin/views/ai_template_views.py
- backend/app/crud/base.py
- backend/app/crud/ai/personality.py
- backend/database/init/03_sample_data.sql
- docs/spec/ai/llm-interaction.md
- docs/data-dict/ai-configuration.md
- docs/api/*
