# AI对话状态

管理对话过程中的消息缓冲、上下文和请求日志。

## ai_message_buffer

消息缓冲窗口表；将用户端多条消息聚合为一个窗口，驱动双计时器逻辑（micro/macro）并控制抢占。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
aggregate_state -- 0=WAKE, 1=OPEN, 2=LOCKED, 3=COMPLETE, 4=CANCELLED
micro_expires_at_ms -- 微计时器到期时间（毫秒）
macro_expires_at_ms -- 宏计时器到期时间（毫秒，可为空）
buffer_expires_at_ms -- 缓冲窗口到期时间（毫秒）
wake_expires_at_ms -- Wake timer expiration (ms), NULL if already awake or in OPEN state
last_message_category -- VARCHAR(32)，CONTENT_TYPING / CONTENT_NO_TYPING / typing_start / typing_end
first_msg_id_client -- 窗口内第一条客户端消息ID
last_msg_id_client -- 窗口内最后一条客户端消息ID
message_count -- 窗口内消息条数，默认1
last_msg_time_ms -- 窗口最后一条消息的毫秒时间戳
locked_at -- 进入 LOCKED 状态的时间（用于超时检测）
wake_adjustment_count -- Number of times wake time was adjusted by new messages
created_at
updated_at
```

## ai_conversation_state

AI 对话状态表，管理对话状态和待发送消息队列。

```txt
user_qiao_id -- 用户 external ID（主键之一）
instance_qiao_id -- AI instance external ID（主键之一）
pending_messages -- 待发送消息队列，JSONB 数组格式
interrupted_at -- 对话被用户消息打断的时间戳
created_at
updated_at
```

## ai_conversation_items

对话历史表，使用简单字段存储消息内容（不再直接存储 LLM provider block）。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- system / user / assistant
message_type -- text / image / audio
text_content -- 文本内容（message_type=text 必填）
media_url -- 媒体地址（message_type=image/audio 必填）
media_metadata -- JSONB 元数据（如宽高、时长、transcript 等）
client_msg_ids -- 聚合的客户端消息ID
buffer_id -- 关联 ai_message_buffer.id，user 必填、assistant 可选
is_excluded_from_context -- 是否从 LLM 上下文中剔除（攻击/敏感内容），默认false
created_at
```

## ai_conversation_items_archive

与主表结构一致，存放冷数据（同样使用 message_type/text_content/media_* 字段）。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- system / user / assistant
message_type -- text / image / audio
text_content -- 文本内容
media_url -- 媒体地址
media_metadata -- 媒体元数据
client_msg_ids -- 客户端消息ID
buffer_id -- 原始缓冲窗口ID
is_excluded_from_context -- 是否排除上下文
created_at -- 原始创建时间
archived_at -- 归档时间
```

## ai_request_logs

AI请求日志表，记录所有AI请求和响应（包括生产环境和测试环境）。

```txt
id -- Snowflake ID
instance_id -- 关联ai_instances.id
user_id -- 关联users.id
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
request_type -- 请求类型：production（生产环境）或test（测试环境），默认production
provider_name -- LLM提供商名称（如doubao, openai, mock等）
model_name -- 使用的模型名称
request -- 请求内容，JSONB格式
response -- 响应内容，JSONB格式
status -- 请求状态：1=success, 2=failed, 3=timeout
token_count -- 消耗的token数量
response_time -- 响应时间（毫秒）
llm_config_id -- 使用的LLM配置ID
buffer_id -- 关联的 ai_message_buffer.id（assistant 消息）
created_at -- 请求创建时间
completed_at -- 请求完成时间
```
