# LLM配置

管理LLM提供商、运行时配置和测试日志。

## llm_providers

LLM提供商配置表，管理不同的大模型提供商信息。

```txt
id -- 自增ID
name -- 提供商标识，如doubao、openai、claude等（允许重复）
display_name -- 显示名称（必须唯一，用于区分同一 Provider 的不同配置）
api_key_env -- API Key 环境变量名（可选，默认为 {NAME}_API_KEY）
base_url -- API基础URL
default_model -- 默认模型名称
supports_streaming -- 是否支持流式输出：1=yes, 0=no
supports_json_schema -- 是否支持JSON Schema：1=yes, 0=no
supports_thinking -- 是否支持思考模式：1=yes, 0=no
created_at
updated_at
```

## llm_configs

LLM运行时配置表，管理具体的模型配置参数。

```txt
id -- 自增ID
provider_id -- 关联llm_providers.id
name -- 配置标识，如primary、backup、test等，唯一
model_name -- 具体模型名称，可选
temperature -- 温度参数，0.0-2.0
max_tokens -- 最大token数
timeout_seconds -- 超时时间（秒）
thinking_mode -- 思考模式：enabled（强制开启）/disabled（强制关闭）/auto（由模型决定）
top_p -- Nucleus Sampling 阈值，[0,1]
frequency_penalty -- 频率惩罚系数，[-2,2]
presence_penalty -- 存在惩罚系数，[-2,2]
stop_sequences -- 停止序列（JSONB，字符串数组）
json_schema_mode -- JSON Schema支持状态
  - 'strict': 已验证支持JSON Schema（测试通过，可用于AI Instance）
  - 'disabled': 已验证不支持JSON Schema（测试失败，仅供查看测试响应）
  - 'auto': 未验证（默认值，需要先测试）
default_tools -- 默认工具定义（JSONB数组），如[{"type": "web_search"}]
default_tool_choice -- 工具选择策略：auto（自动）/none（不使用）/required（必须使用），默认auto
parallel_tool_calls -- 是否允许并行工具调用：1=yes, 0=no，默认0
max_tool_calls -- 单次请求最大工具调用次数，默认1
default_extra_headers -- 默认额外请求头（JSONB），如{"ark-beta-web-search": "true"}
default_extra_query -- 默认额外查询参数（JSONB）
status -- 状态：1=active, 2=inactive
priority -- 优先级，数字越小优先级越高，用于故障转移
extra_params -- 扩展参数（JSONB格式）
  用于存储不在表结构中的扩展配置，如：
  - memory_limits: AI记忆系统限制配置，如 {"core": 30, "recent": 50}
  - 提供商特定参数：如 max_completion_tokens、service_tier 等
  注意：此字段仅用于存储扩展参数，不应覆盖已有的表字段（如 temperature、max_tokens 等）
created_at
updated_at
```

**配置优先级说明**：

LLM 请求参数的配置优先级遵循以下规则（从高到低）：

1. **函数直接参数** - 在调用 `invoke_llm()` 时直接传入的参数（如 temperature、max_tokens）
2. **实例级覆盖** - `ai_instances.request_params` 或 `ai_templates.request_params`（JSONB字段，可覆盖任何参数）
3. **配置级默认值** - `llm_configs` 表中的专用字段（temperature、max_tokens、top_p 等）
4. **配置级扩展参数** - `llm_configs.extra_params`（仅用于不在表结构中的参数，如 memory_limits）
5. **硬编码默认值** - 代码中定义的默认值

**示例场景**：

```python
# llm_configs 表配置
temperature = 0.7
max_tokens = 4000
extra_params = {"memory_limits": {"core": 30, "recent": 50}}

# ai_instances 实例覆盖
request_params = {
    "temperature": 0.9,  # 覆盖 llm_configs.temperature (0.7 → 0.9)
    "memory_limits": {"core": 20, "recent": 40}  # 覆盖 extra_params.memory_limits
}

# 最终生效的参数
temperature = 0.9  # 来自 instance.request_params
max_tokens = 4000  # 来自 llm_configs.max_tokens（未被覆盖）
memory_limits = {"core": 20, "recent": 40}  # 来自 instance.request_params
```

**设计说明**：

- **为什么允许实例级覆盖配置级参数？**
  - 提供实例级个性化能力（如特定AI需要更高的 temperature）
  - 支持 A/B 测试和临时调整
  - 符合"配置继承与覆盖"的常见设计模式

- **`extra_params` 的正确用途**：
  - ✅ 存储扩展参数（memory_limits、provider 特定参数等）
  - ✅ 避免频繁修改数据库 schema
  - ❌ 不应用于覆盖已有字段（会造成混淆和冗余）

## llm_test_logs

LLM配置测试日志表，专门记录通过管理后台进行的LLM配置测试。

```txt
id -- Snowflake ID
config_id -- 关联llm_configs.id
config_name -- 配置名（冗余字段，便于查询）
provider_name -- Provider名称（冗余字段）
model_name -- 使用的模型名称
test_message -- 测试消息内容，TEXT类型
override_temperature -- 覆盖的温度参数（0.0-2.0）
override_max_tokens -- 覆盖的最大token数
thinking_mode -- 思考模式：enabled / disabled / auto
enable_json_schema -- 是否启用json_schema
request -- 完整请求payload，JSONB格式
response -- 完整响应数据，JSONB格式
status -- 状态：1=success, 2=failed, 3=timeout
error_message -- 错误信息（如果失败），TEXT类型
response_time_ms -- 响应时间（毫秒）
prompt_tokens -- 提示词token数
completion_tokens -- 完成token数
total_tokens -- 总token数
reasoning_content -- 思考过程内容（思考模式启用时），TEXT类型
created_at -- 测试创建时间
completed_at -- 测试完成时间
```
