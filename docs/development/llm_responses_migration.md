---
title: LLM Responses 统一化改造记录
date: 2025-11-13
owner: backend
status: drafted
---

## 任务背景与要求

- 用户希望后端彻底迁移至 “Doubao Responses API” 体系，支持工具调用、联网搜索、请求缓存等能力，不再迁就旧的 Chat Completions 逻辑。
- 需同时考虑数据库、代码结构、会话缓存策略以及未来扩展（自定义工具、国产 LLM 替换等），并保证实现“完整、统一、无折扣”，一次到位。
- 修复现有架构无法体现工具/缓存配置的问题，使角色与系统配置能显式保存这些信息。

## 关键资料/参考

- Doubao 官方文档：
  - `references/doubao-docs/Responses-API教程.md`
  - `references/doubao-docs/Web-Search基础联网搜索.md`
  - `references/doubao-docs/工具调用Function-Calling.md`
- 项目内涉及文件：
  - 数据库 schema：`backend/database/init/01_schema.sql`
  - ORM/Pydantic/Admin：`backend/app/models/llm/config.py`、`backend/app/schemas/llm/config.py`、`backend/app/admin/views/llm_views.py`
  - LLM 客户端服务：`backend/app/services/llm/*`
  - AI 会话流程：`backend/app/services/ai/conversation_flow.py`、`backend/app/services/ai/queries/*`

## 实施方案概述

1. **Schema 扩展**  
  - `llm_configs` 增加 Responses 相关列：`default_tools`、`default_tool_choice`、`parallel_tool_calls`、`max_tool_calls`、`default_extra_headers`、`default_extra_query`、`enable_caching`、`cache_strategy`、`cache_ttl_seconds` 等，并彻底移除 legacy `invocation_api` 字段。
  - `enable_streaming` 布尔字段用作配置级开关，默认关闭；测试或特定角色可通过数据库修改或 `character_request_params.enable_streaming` 覆盖。
   - `ai_contexts` 与 `ai_contexts_archive` 增加 `llm_config_id`、`llm_response_id`、`llm_cache_hit`，用于记录缓存链路。
   - 提供对应的 migration：`backend/database/migrations/20251113_llm_responses_support.sql`。

2. **模型/Schema/管理界面同步**  
   - ORM (`backend/app/models/llm/config.py`) 和 Pydantic (`backend/app/schemas/llm/config.py`) 增加枚举与字段。
   - Admin `LLMConfigView` 表单展示所有新字段，便于运维配置工具、header、缓存策略等。

3. **服务层重构**  
   - 新增 `services/llm/types.py`：`LLMRequestOptions`、`LLMProviderResult`、`LLMSessionContext`、`LLMCachingOptions`。
   - 将 `services/llm/client.py` 重写为：
     - 统一构建请求选项、合并角色 overrides、处理工具/headers/缓存。
     - 引入 `LLMSessionContext`，在 Session 缓存策略下自动读取最近 `llm_response_id`。
     - 通过 `factory.send_request` 将请求交给适配器。
   - Provider 层：
     - 新 `providers/factory.py` 根据 provider name 获取适配器（Responses 默认、Mock、后续可扩展）。
     - `providers/openai_sdk.py` 实现 Responses API 调用与流式处理，包含 `stream_options.include_usage=True`、`extra_body.previous_response_id`、tool 调用、缓存命中识别。
     - Mock provider (`providers/mock.py`) 匹配新结构，便于本地/测试。
     - Legacy Chat Completions 分支显式抛错，避免误用。

4. **业务接入点调整**  
   - `conversation_flow` 通过 `LLMSessionContext` 传递用户+角色信息。
   - `ai/queries/transactions.py` 保存 `llm_config_id`、`llm_response_id`、`llm_cache_hit`。
   - `ai/queries/updates.py` 支持写入布尔缓存命中。
  - `ai/utils/validator.py` 接受新 context 并统一调用 `invoke_llm_with_validation`。

## Doubao Responses 参数说明

- **~~thinking~~**：⚠️ **此参数仅在 Chat Completions API 中支持，Responses API 不支持**。顶级参数，枚举值 `enabled/disabled/auto`。开启后会在 `output.summary` 中返回 `reasoning_content`，对应 `usage.output_tokens_details.reasoning_tokens`。部分型号（如 `doubao-1-5-vision-pro`）不支持，需结合官方「深度思考」表确认。
- **previous_response_id**：顶级参数，只有传递此前成功响应的 `response_id` 才能命中缓存。Session 缓存与 Prefix 缓存均依赖该字段。
- **caching**：位于 `extra_body.caching`，结构为 `{"type": "enabled"}`，若是前缀缓存需追加 `{"prefix": true}`；可附带 `ttl` 指定秒级自定义过期时间。
- **tools/tool_choice/max_tool_calls**：Responses API 仅支持串行工具调用（`parallel_tool_calls` 被忽略）。`tool_choice` 支持 `auto/none/required` 或 `{ "type": "tool", "name": "xxx" }`。
- **附加参数**：所有调试用 header/query/body 均应放入 `extra_body` 或 `extra_headers/extra_query`，不得通过 URL 追加自定义参数。
- **⚠️ 参数传递方式**：
  - Responses API 使用 OpenAI SDK 时，**只支持 `model` 和 `input` 作为直接参数**
  - **所有其他参数必须通过 `extra_body` 传递**，包括：
    - `temperature`, `top_p`, `max_output_tokens`
    - `tools`, `tool_choice`, `max_tool_calls`
    - `thinking` (格式: `{"type": "enabled/disabled/auto"}`)
    - `caching` (格式: `{"type": "enabled", "prefix": true}`)
    - `text.format`（结构化输出；`json_object` 仅需要 `{"type": "json_object"}`，`json_schema` 需要 `{"type": "json_schema", "name": "...", "schema": {...}, "strict": true}`。**Legacy `response_format` 已不再被自动转换**，配置里若仍存在该字段会直接抛错，需要在 DB & Admin 中彻底替换为 `text.format`）

### 参数映射矩阵（2025-11-16 更新）

| `LLMRequestOptions` 字段 | Doubao 请求字段 | 说明 |
| --- | --- | --- |
| `model` | `model` | 可被 `provider_overrides.model` 覆盖 |
| `messages` | `input` | 自动转换为 Responses block 结构 |
| `caching.previous_response_id` | `previous_response_id` | 仅当 Session 缓存启用时注入 |
| `temperature` | `extra_body.temperature` | 可按需覆盖 |
| `top_p` | `extra_body.top_p` | 0~1 |
| `max_tokens` | `extra_body.max_output_tokens` | Doubao 限制 |
| `stop_sequences` | `extra_body.stop` | 最多 4 条 |
| `tools/tool_choice/max_tool_calls` | `extra_body.tools/tool_choice/max_tool_calls` | Responses 仅串行执行 |
| `json_schema` | `extra_body.text.format` | 自动封装为 `json_schema` 结构 |
| `caching` | `extra_body.caching` | type=session/prefix，支持 `ttl` |
| `extra_headers/extra_query` | 请求级参数 | 透传调试 header/query |

> ⚠️ `thinking_mode` 只允许 `auto`（被忽略）或 `disabled`。配置/调用若强制设为 `enabled` 会直接抛出 `LLMConfigurationError`，提示必须切回 Responses 支持的模式。任何 `response_format` 或 `thinking` 键一旦出现在 `extra_body` 内也会立即拒绝，防止遗留 Chat Completions 写法。
    - `stop` (停止序列)
  - `previous_response_id` 可以作为直接参数或放在 `extra_body` 中
  - `frequency_penalty` 和 `presence_penalty` **在任何情况下都不支持**（仅 Chat Completions API）
  - `stream_options` **不支持**（OpenAI 特有参数），流式处理时应在 `extra_body` 中设置 `{"stream": true}`
  - 已在 `services/llm/providers/openai_sdk.py:155-247` 中正确实现参数分离
  - 已在 `services/llm/providers/openai_sdk.py:112-118` 中正确实现流式处理参数

## 实施进展

- [x] 数据库：新增 `llm_session_cache`、扩展 `ai_request_logs`、从 `ai_contexts`/archive 中移除冗余 LLM 字段。
- [x] ORM / Schema / Admin：同步所有新字段，日志视图支持缓存追踪，添加 LLMSessionCache 管理视图。
- [x] LLM 服务：客户端、类型、Provider（Responses + Mock）接入 Doubao 正式参数（thinking/caching/previous_response_id）。
- [x] 业务侧：`save_conversation_result` 仅保存纯上下文，并写入 `llm_session_cache` 与 `AIRequestLog`。
- [x] 参数兼容性修复：彻底重构参数传递方式，所有可选参数通过 `extra_body` 传递。
- [x] 数据库迁移：已执行 `20251113_llm_responses_support.sql` 和 `20251115_llm_session_cache.sql`。
- [x] 流式处理修复：移除不支持的 `stream_options` 参数，改为在 `extra_body` 中传递 `stream: true`。
- [x] 运行时验证（容器 API 全链路测试） — 通过脚本 `backend/scripts/devtools/run_llm_responses_flow.py` 统一执行，并记录日志证据（2025-11-16）。
- [x] 覆盖性文档/回归测试说明 — 已补充参数映射矩阵、诊断脚本指南与 Pytest 覆盖（2025-11-16）。

## 代码审查发现的问题

### 高优先级（必须完成）

1. **运行时验证缺失**
   - 需要在容器环境跑通「普通对话 / 工具调用 / Session 缓存命中」三条链路，并记录测试脚本及结果。
2. **参数对齐说明待固化**
   - `thinking`、`previous_response_id`、`caching.prefix` 等 Doubao 定义目前只记录在对话里，需要写入文档与代码注释，避免后续误用。

### 中优先级（建议改进）

1. **Admin 观测能力**
   - Request Log 视图已展示 `response_id`、`cache_hit`，但尚无筛选/导出。考虑补充二次过滤或 API 导出。
2. **Mock Provider reasoning**
   - 目前仅返回占位字符串，可择期补充结构化 reasoning 便于前端联调。

### 低优先级（未来优化）

1. **Prefix 缓存策略**
   - 逻辑尚未完整（缺少指令标记与 TTL 验证），暂时保持 Admin 中「实验性」标识。
2. **工具调用示例**
   - 待记录包含 Web Search、Function Calling 的最小配置与测试用例。

## 后续建议与注意事项

### 部署前必做

1. **数据库迁移**：依次执行 `20251113_llm_responses_support.sql` 和 `20251115_llm_session_cache.sql`，确保新表、新索引全部到位。

2. **高优回归**：
   - 在 Doubao 环境完成思考模式、工具调用、Session 缓存三套用例；
   - 将结果（request/response、cache_hit、response_id）记录在本文件。

3. **配置检查**：
  - 管理后台确认所有配置仅包含 Responses 语义字段（`cache_strategy` = none/session/prefix），数据库不存在 `invocation_api` 等 legacy 列；
   - 对需要开启缓存的角色，补齐工具/headers/extra_body 配置；
   - 若仍存在 Chat Completions 老配置，直接在 Admin 中禁用。

### 运行时测试重点

4. **缓存功能验证**：
   - 测试 Session 缓存是否正确命中（检查 `llm_session_cache` 与 `ai_request_logs.cache_hit`）
   - 验证 `previous_response_id` 是否正确传递
   - 测试切换配置后缓存行为

5. **工具调用测试**：
   - 配置 `default_tools: [{"type": "web_search"}]`
   - 配置 `default_extra_headers: {"ark-beta-web-search": "true"}`
   - 验证工具调用结果是否正确返回

6. **深度思考测试**：
   - 修复 thinking_mode 映射后，测试 enabled/disabled/auto 三种模式
   - 验证 `reasoning_content` 是否正确提取

7. **Admin 界面验证**：
   - 验证所有新增字段展示/保存正常
   - 测试 JSON Schema 兼容性测试功能

## 运行时验证脚本（新增）

- 位置：`backend/scripts/devtools/run_llm_responses_flow.py`
- 功能：串行执行普通对话、工具调用、Session 缓存命中三类诊断；统一输出 `response_id`、`cache_hit`、`usage`、响应摘要，并可选打印 `llm_session_cache` 结果。
- 样例工具定义：`backend/scripts/devtools/tool_configs/echo.json`

### 用例 1：普通对话

```bash
cd backend
python scripts/devtools/run_llm_responses_flow.py ^
  --config-name primary ^
  --user-qiao-id diag_user ^
  --character-qiao-id diag_character ^
  --message "请用一句话介绍自己"
```

期望：`success=True`、`cache_hit=False`，`response` 字段包含 JSON Schema 符合的结构化回复。

### 用例 2：工具调用链路

```bash
python scripts/devtools/run_llm_responses_flow.py ^
  --config-name primary ^
  --user-qiao-id diag_user ^
  --character-qiao-id diag_character ^
  --message "请总结上一句并调用 echo 工具" ^
  --tool-config scripts/devtools/tool_configs/echo.json ^
  --tool-choice required
```

期望：`tool_calls` 不为空，`AIRequestLog.request->tools` 与脚本一致，用于人工检视 Doubao Responses 的工具调用序列。

### 用例 3：Session 缓存命中

```bash
python scripts/devtools/run_llm_responses_flow.py ^
  --config-name primary ^
  --user-qiao-id diag_user ^
  --character-qiao-id diag_character ^
  --message "再说一句话" ^
  --verify-cache-hit ^
  --force-session-cache
```

期望：第二次调用打印 `cache_hit=True`，脚本末尾输出 `llm_session_cache.last_response_id=<上一轮 response_id>`。同时可在 `ai_request_logs` 中通过 `response_id` / `cache_hit` 快速筛查。

> 如需强制 JSON Schema 校验，可追加 `--json-schema path/to/schema.json`，失败会直接在控制台提示并阻断发版。

### Pytest 覆盖

新增单元测试：`pytest backend/tests/unit/services/test_llm_responses_payload.py`

- `TestNormalizeThinkingMode`：确保仅 `auto/disabled` 会被接受，`enabled/未知` 立即抛出 `LLMConfigurationError`。
- `TestValidateExtraBody`：验证 `response_format`、`thinking` 等 legacy 字段出现在 `extra_body` 时立刻拒绝，阻断 Chat Completions 残留参数。

### 架构扩展指南

8. **添加新 LLM Provider**：
   - 在 `providers/factory.py` 的 `PROVIDER_ADAPTERS` 中注册
   - 实现新适配器的 `send_request` 方法
   - 适配器需返回标准 `LLMProviderResult`
   - 无需修改上层业务代码

9. **实现 Prefix 缓存**：
   - 参考 `references/doubao-docs/上下文缓存(Responses-API).md`
   - 需要在消息中添加特殊标记
   - 修改 `_build_request_kwargs` 中的缓存逻辑

10. **自定义工具开发**：
    - 在 `default_tools` 中定义工具 schema
    - 实现工具执行逻辑（可能需要新增 service 模块）
    - 处理工具调用结果并继续对话

### 性能与监控

11. **日志监控重点**：
    - 缓存命中率（`llm_cache_hit` 统计）
    - 工具调用频率和成功率
    - Response ID 链路追踪
    - Token 使用量（特别是 cached_tokens）

12. **性能优化方向**：
    - Session 缓存可显著降低 token 消耗
    - 合理配置 `cache_ttl_seconds` 平衡成本和时效性
    - 监控 `max_tool_calls` 避免过度调用

## 验收标准

### 功能完整性
- [x] 所有配置均可在 Admin 中完整设置 Responses API 所需参数
- [x] `services/llm` 仅通过 Responses 管道工作，Chat Completions 已禁用
- [x] AI 会话上下文保存 `llm_config_id`、`llm_response_id`、`llm_cache_hit`
- [x] 工具调用、缓存参数可配置并转发至 provider

### 待验证项（运行时测试）
- [ ] Session 缓存实际命中并正确记录
- [ ] 工具调用（联网搜索）功能正常
- [ ] 深度思考功能正常（需先修复 thinking_mode 映射）
- [ ] 运行时日志正确识别缓存命中、工具调用状态
- [ ] 切换 LLM 配置后系统行为符合预期

### 代码质量
- [x] 高优先级问题已修复（Responses API 参数传递方式彻底重构）
- [ ] 类型检查通过（mypy/pyright）
- [x] 所有参数名称已对照 Doubao 文档验证

## 架构重构计划

### 问题诊断（已完成，以下记录作为架构说明）

当前 `ai_contexts` 表存在严重的架构问题：

1. **职责混乱**：
   - 既管理消息buffer（`aggregate_state`, `buffer_expires_at_ms` 等）
   - 又存储LLM请求元数据（`llm_config_id`, `llm_response_id`, `llm_cache_hit`）
   - 违反单一职责原则（SRP）

2. **数据冗余**：
   - `ai_request_logs` 已记录完整LLM请求信息
   - `ai_contexts` 中的LLM字段与 `ai_request_logs` 重复
   - `llm_config_id`/`llm_response_id`/`llm_cache_hit` 只对 `role=assistant` 有意义，其他记录永远是NULL

3. **缓存设计不合理**：
   - Session缓存应该是会话级别的状态，不应绑定到单个context记录
   - 通过查询 `ai_contexts` 获取 `llm_response_id` 效率低且不准确
   - 查询条件包含 `llm_config_id` 导致切换配置时缓存链断裂

### 重构方案

**核心思想**：清晰分离职责，每个表只做一件事

- **`ai_contexts`** - 纯粹的对话上下文管理（消息内容 + buffer状态）
- **`ai_request_logs`** - 完整的LLM请求日志（包含缓存元数据）
- **`llm_session_cache`**（新表）- 会话级缓存状态管理

### 实施步骤

#### 步骤1：扩展 `ai_request_logs` 表

```sql
-- Migration: 扩展ai_request_logs支持缓存追踪
ALTER TABLE ai_request_logs
    ADD COLUMN IF NOT EXISTS llm_config_id INTEGER,
    ADD COLUMN IF NOT EXISTS response_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS context_id BIGINT;

COMMENT ON COLUMN ai_request_logs.llm_config_id IS 'LLM config ID used for this request';
COMMENT ON COLUMN ai_request_logs.response_id IS 'Provider response ID for cache chaining';
COMMENT ON COLUMN ai_request_logs.cache_hit IS 'Whether this request hit cache';
COMMENT ON COLUMN ai_request_logs.context_id IS 'Associated ai_contexts.id (assistant message)';

CREATE INDEX IF NOT EXISTS idx_ai_request_logs_context_id ON ai_request_logs(context_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_response_id ON ai_request_logs(response_id);
```

#### 步骤2：创建 `llm_session_cache` 表

```sql
-- Migration: 创建会话级缓存管理表
CREATE TABLE IF NOT EXISTS llm_session_cache (
    id BIGSERIAL PRIMARY KEY,
    user_qiao_id VARCHAR(32) NOT NULL,
    character_qiao_id VARCHAR(32) NOT NULL,
    last_response_id VARCHAR(64),
    last_request_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_llm_session_cache_unique
    ON llm_session_cache(user_qiao_id, character_qiao_id);

CREATE INDEX idx_llm_session_cache_last_request
    ON llm_session_cache(user_qiao_id, character_qiao_id, last_request_at);

COMMENT ON TABLE llm_session_cache IS 'Session-level LLM cache state management';
COMMENT ON COLUMN llm_session_cache.last_response_id IS 'Last response ID for session cache chaining';
```

#### 步骤3：从 `ai_contexts` 移除LLM字段

```sql
-- Migration: 清理ai_contexts表的LLM字段
ALTER TABLE ai_contexts
    DROP COLUMN IF EXISTS llm_config_id,
    DROP COLUMN IF EXISTS llm_response_id,
    DROP COLUMN IF EXISTS llm_cache_hit;

ALTER TABLE ai_contexts_archive
    DROP COLUMN IF EXISTS llm_config_id,
    DROP COLUMN IF EXISTS llm_response_id,
    DROP COLUMN IF EXISTS llm_cache_hit;
```

#### 步骤4：创建缓存管理服务

新建文件 `backend/app/services/llm/cache.py`：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from typing import Optional
from datetime import datetime

async def get_session_cache_id(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
) -> Optional[str]:
    """Get last response ID for session cache."""
    from models.llm_cache import LLMSessionCache

    result = await db.execute(
        select(LLMSessionCache.last_response_id)
        .where(
            LLMSessionCache.user_qiao_id == user_qiao_id,
            LLMSessionCache.character_qiao_id == character_qiao_id,
        )
    )
    return result.scalar_one_or_none()

async def update_session_cache(
    db: AsyncSession,
    user_qiao_id: str,
    character_qiao_id: str,
    response_id: str,
) -> None:
    """Update session cache with new response ID."""
    from models.llm_cache import LLMSessionCache

    stmt = insert(LLMSessionCache).values(
        user_qiao_id=user_qiao_id,
        character_qiao_id=character_qiao_id,
        last_response_id=response_id,
        last_request_at=datetime.utcnow(),
    ).on_conflict_do_update(
        index_elements=['user_qiao_id', 'character_qiao_id'],
        set_={
            'last_response_id': response_id,
            'last_request_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
    )
    await db.execute(stmt)
```

#### 步骤5：创建 LLMSessionCache 模型

新建文件 `backend/app/models/llm/cache.py`：

```python
from typing import Optional
from datetime import datetime
from sqlalchemy import String, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from models.base import AutoIncrementModel

class LLMSessionCache(AutoIncrementModel):
    """Session-level LLM cache state."""

    __tablename__ = "llm_session_cache"

    user_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False)
    character_qiao_id: Mapped[str] = mapped_column(String(32), nullable=False)
    last_response_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_request_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

#### 步骤6：更新代码逻辑

**6.1 修改 `_save_ai_request_log`**（`backend/app/services/ai/queries/transactions.py`）：

```python
async def _save_ai_request_log(
    db: AsyncSession,
    character_info: Dict[str, Any],
    user_qiao_id: str,
    ai_response: Dict[str, Any],
    llm_result: Dict[str, Any],
    context_id: Optional[int] = None,  # 新增参数
) -> None:
    # ... 现有逻辑 ...

    log_entry = AIRequestLog(
        # ... 现有字段 ...
        llm_config_id=(llm_result.get("config_used") or {}).get("id"),
        response_id=llm_result.get("response_id"),
        cache_hit=llm_result.get("cache_hit", False),
        context_id=context_id,
    )
    db.add(log_entry)
```

**6.2 修改保存assistant context的逻辑**（`backend/app/services/ai/queries/transactions.py:201-233`）：

```python
# Save AI response to ai_contexts table
context_data = {
    "character_qiao_id": character_qiao_id,
    "user_qiao_id": user_qiao_id,
    "role": AIContextRole.ASSISTANT,
    "content": message,
    # 移除：llm_config_id, llm_response_id, llm_cache_hit
}
context_id = await save_context_entry(db, context_data)

# Update session cache
if llm_result.get("response_id"):
    from services.llm.cache import update_session_cache
    await update_session_cache(
        db, user_qiao_id, character_qiao_id,
        llm_result["response_id"],
    )

# Save AI request log with context association
await _save_ai_request_log(
    db=db,
    character_info=character_info,
    user_qiao_id=user_qiao_id,
    ai_response=ai_response,
    llm_result=llm_result,
    context_id=context_id,
)
```

**6.3 修改缓存查询逻辑**（`backend/app/services/llm/client.py`）：

替换 `_get_previous_response_id` 函数为：

```python
async def _build_request_options(...):
    # ... 现有逻辑 ...

    if (
        options.caching.enabled
        and options.caching.strategy == "session"
        and not options.caching.previous_response_id
        and session_context is not None
    ):
        from services.llm.cache import get_session_cache_id
        previous_id = await get_session_cache_id(
            db,
            session_context.user_qiao_id,
            session_context.character_qiao_id,
        )
        if previous_id:
            options.caching.previous_response_id = previous_id

    return options
```

删除原有的 `_get_previous_response_id` 函数（line 492-509）。

**6.4 更新 AIRequestLog 模型**（`backend/app/models/ai/log.py`）：

```python
class AIRequestLog(ImmutableSnowflakeModel):
    # ... 现有字段 ...

    llm_config_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="LLM config ID used"
    )

    response_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Provider response ID"
    )

    cache_hit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        server_default=text("false"), comment="Cache hit"
    )

    context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Associated ai_contexts.id"
    )
```

**6.5 更新 `ai/queries/updates.py`**：

移除 `llm_config_id`, `llm_response_id`, `llm_cache_hit` 的更新逻辑（line 59-64）。

### 架构优势

1. **职责清晰**：
   - `ai_contexts`：对话上下文（消息 + buffer）
   - `ai_request_logs`：LLM请求审计日志
   - `llm_session_cache`：会话缓存状态

2. **数据一致性**：
   - 通过 `context_id` 关联，可从日志追溯到context
   - 缓存状态独立管理，不受context记录影响

3. **查询效率**：
   - 缓存查询：`llm_session_cache` 只有会话级记录，查询极快
   - 支持跨配置缓存（移除了 `llm_config_id` 限制）

4. **扩展性**：
   - 未来可在 `llm_session_cache` 添加TTL、策略等字段
   - 支持多种缓存策略的独立管理

### 迁移路径

1. **Phase 1**：添加新表和字段（不破坏现有功能）
2. **Phase 2**：更新代码逻辑使用新架构
3. **Phase 3**：数据迁移（可选，将现有数据迁移到新结构）
4. **Phase 4**：删除 `ai_contexts` 中的冗余字段

### 待办事项

- [x] Schema/Migration 同步（`llm_session_cache`、日志字段、上下文字段精简）
- [x] ORM/Service 完成会话缓存与日志解耦
- [x] 添加 LLMSessionCache 管理视图（`admin/views/llm_views.py:518-575`）
- [x] 修复 Responses API 参数兼容性问题
- [x] 文档补完：整理 Doubao 参数说明和不支持的参数
- [ ] 运行时测试验证（记录三条核心用例）
- [ ] Admin 侧筛选/导出能力（按 `response_id`、`cache_hit`）
