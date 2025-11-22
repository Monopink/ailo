# AI 实例命名重构任务进展记录

## 任务背景与目标

- 将 `ai_instance*` 相关表、字段、API、模型、管理端与小程序视图全面迁移到新的命名体系：`ai_instances`（实例）、`ai_personas`（档案）、`ai_templates`（模板）、`square_type_entries`（广场推荐）。
- 完全对齐数据库初始化脚本、ORM、Service、CRUD、日志、队列、LLM 配置与文档，避免 legacy 命名在任何模块残留。
- 保持 `docs/task/ai-persona-architecture.md` 作为架构基线，所有变更需与其语义同步、并在本推进表中记录。

## 已实施内容（截至当前）

1. **数据库与模型**
   - SQL 初始脚本 (`backend/database/init/01_schema.sql`、`03_sample_data.sql`) 已使用 `ai_instances`、`ai_personas`、`ai_instance_dimensions`、`ai_templates` 等命名，索引/触发器均指向新表。
   - ORM 层 (`models.ai.instance.py`、`instance_dimension.py`、`ai_request_log.py`) 复用了新表名，Admin View/CRUD 也指向 `AIInstancePromise` 命名。

2. **服务与查询**
   - `InstanceContext` 取代 `CharacterContext`，`services.ai` 下的 prompt、relationship、conversation、memory、message buffer/scanner 等模块全改用 `instance_*` 命名。
   - `services.ai.queries` 支出 `get_instance_context`、`get_instance_relationship_scores`、`get_instance_relationship_config`、`get_all_instances`，相关 `updates.py`、`transactions.py` 调用同样切换。
   - `services.ai.relationship_scoring` / `services.ai.queries.transactions` / `services.ai.conversation_flow` / `services.ai.conversation_memory` 等已统一使用 new logs (`instance_context_loaded`、`instance_relationship_scores_retrieved` 等)。

3. **管理端与 API**
   - Starlette Admin 的 `AI_INSTANCE_VIEWS`、`ai_instance_router`、`ai_instance_chat_test_view` 均使用新名称，Admin API 路由 `admin_api_router.include_router(ai_instance_router, prefix="/ai", tags=["Admin AI Instance"])`。
   - Admin 相关异步服务（`services/admin/instance_relationship.py`、`services/admin/testing/instance_chat`）也改名为 instance-oriented 逻辑。

4. **LLM / 消息层**
   - LLM 客户端使用 `instance_request_params`（替代旧 `character_request_params`），`services/llm/client.py` 的 `_call_provider`/`_build_request_options` 接收的是 instance 参数。
   - `services/ai/queries/transactions.process_llm_response`、`services/message/security/validation`、`message.buffer/scanner` 现在都引入 new queries，连锁日志、错误码都跟进。
   - `services.message.processing.buffer`、`scanner` 所依赖的 `get_instance_relationship_config` 也直接从 `services.ai.queries.instance_queries` 引入。

5. **测试/文档同步**
   - 进度记录已同步至本文件；移除旧 `character` 命名的测试文件后重新添加 `backend/tests/unit/services/test_instance_queries.py` 以验证 `_relationship_config` 逻辑。
   - `docs/task/ai-instance-llm-config-assignment.md`、`docs/development/contact-request-flow.md` 等尚未重写，计划集中更新一轮。

## 尚未完成 / 待处理事项

1. **文档/原型**  
   - `docs/task/ai-instance-llm-config-assignment.md`、`docs/development/contact-request-flow.md`、`docs/prototype/*` 等已经迁移为 `instance_*`/`instance_profile`、`create_instance_from_persona` 表述，后续继续验证没有残余 `character` 关键字。
2. **前端/模板**  
   - 微信小程序 (`frontend/wx-minipg`) 与 Admin 模板（`ai_instance_chat_test.html`、`ai_advanced_edit_views.py`、`ai_instance_chat_test_view.py`）仍包含“Character”文案，待统一更新为“Instance/Persona” UX。
3. **LLM & 测试工具**  
   - `services/admin/testing/llm_config.py`、`services/message/security/validation.py`、`services/admin/testing/instance_chat/__init__.py` 中的 `character` 术语需彻底重写，确保所有上下文都使用 `instance`/`persona`。
4. **测试验证**  
   - 所有重命名后还未跑一轮 `pytest` 或后端/管理端冒烟；后续快照需执行数据库初始化 + `pytest`，并对关键 API/管理端/小程序进行基本联调。

## 下一步计划

1. 先完成文档与前端文本替换（`docs/task/ai-instance-llm-config-assignment.md`，`docs/development/contact-request-flow.md`，`frontend/wx-minipg` 视图），确保对外描述一致。
2. 与 LLML 及测试辅助模块（`services.llm`、`services/admin/testing/llm_config.py`、`services/message/security/validation.py`）对接，替换掉残余 `instance_request_params`/`INSTANCE_BLOCKED_*` 等关键字。
3. 运行 `pytest` + 关键冒烟（包括 conversation flow、admin API、小程序关键页面）并记录结果。
4. 重新运行 `rg character` 确认无漏洞，整理 diff 与日志后准备下一轮 PR 复查。
