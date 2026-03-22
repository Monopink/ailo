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
thinking_mode -- 思考模式（enum: ThinkingMode）
top_p -- Nucleus Sampling 阈值，[0,1]
frequency_penalty -- 频率惩罚系数，[-2,2]
presence_penalty -- 存在惩罚系数，[-2,2]
stop_sequences -- 停止序列（JSONB，字符串数组）
json_schema_mode -- JSON Schema支持状态
default_tools -- 默认工具定义（JSONB数组），如[{"type": "web_search"}]
default_tool_choice -- 工具选择策略（enum: ToolChoice）
parallel_tool_calls -- 是否允许并行工具调用：1=yes, 0=no，默认0
max_tool_calls -- 单次请求最大工具调用次数，默认1
default_extra_headers -- 默认额外请求头（JSONB），如{"ark-beta-web-search": "true"}
default_extra_query -- 默认额外查询参数（JSONB）
status -- 状态（enum: LLMConfigStatus）
priority -- 优先级，数字越小优先级越高，用于故障转移
extra_params -- 扩展参数（JSONB格式）
created_at
updated_at
```

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
status -- 状态（enum: LLMTestStatus）
error_message -- 错误信息（如果失败），TEXT类型
response_time_ms -- 响应时间（毫秒）
prompt_tokens -- 提示词token数
completion_tokens -- 完成token数
total_tokens -- 总token数
reasoning_content -- 思考过程内容（思考模式启用时），TEXT类型
created_at -- 测试创建时间
completed_at -- 测试完成时间
```
