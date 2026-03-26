# AI对话状态

管理对话过程中的消息缓冲、上下文和请求日志。

## ai_message_buffer

消息缓冲窗口表；将用户端多条消息聚合为一个窗口，驱动双计时器逻辑（micro/macro）并控制抢占。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
aggregate_state -- 聚合状态（enum: AIMessageBufferState）
micro_expires_at_ms -- 微计时器到期时间（毫秒）
macro_expires_at_ms -- 宏计时器到期时间（毫秒，可为空）
buffer_expires_at_ms -- 统一调度截止时间（毫秒），由 micro/macro 与 wake 门控共同决定
wake_expires_at_ms -- Wake 门控截止时间（毫秒），未启用门控时为 NULL
last_message_category -- 缓冲消息分类（enum: BufferMessageCategory）
first_msg_id_client -- 窗口内第一条客户端消息ID
last_msg_id_client -- 窗口内最后一条客户端消息ID
message_count -- 窗口内消息条数，默认1
last_msg_time_ms -- 窗口最后一条消息的毫秒时间戳
locked_at -- 进入 LOCKED 状态的时间（用于超时检测）
wake_adjustment_count -- 等待唤醒期间被新消息调整的次数（仅文本消息累加）
created_at
updated_at
```

## ai_conversation_state

AI 对话状态表，管理对话状态和待发送消息队列。

```txt
user_qiao_id -- 用户 external ID（主键之一）
instance_qiao_id -- AI instance external ID（主键之一）
pending_messages -- 被抢占后未发送消息，JSONB 对象：{"outgoing":[],"total_pending":0}
interrupted_at -- 对话被用户消息打断的时间戳
created_at
updated_at
```

## ai_conversation_runtime

会话运行态表，管理跨实例抢占一致性。

```txt
user_qiao_id -- 用户 external ID（主键之一）
instance_qiao_id -- AI instance external ID（主键之一）
ingress_version -- 入站代次，BIGINT，CONTENT_INPUT 到达即单调递增
active_turn_version -- 活跃处理代次，BIGINT，新窗口锁定时推进
created_at
updated_at
```

## ai_conversation_items

对话历史表，使用简单字段存储消息内容。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- 角色（enum: ConversationRole）
message_type -- 消息类型（enum: ConversationItemMessageType）
text_content -- 文本内容（message_type=text 必填）
media_url -- 媒体地址（message_type=image/audio 必填）
media_metadata -- JSONB 元数据（如宽高、时长、transcript 等）
client_msg_ids -- 聚合的客户端消息ID
buffer_id -- 关联 ai_message_buffer.id，user 必填、assistant 可选
is_excluded_from_context -- 上下文状态（enum: ConversationItemContextStatus，默认 INCLUDED）
created_at
```

## ai_conversation_items_archive

与主表结构一致，存放冷数据（同样使用 message_type/text_content/media_* 字段）。

```txt
id -- Snowflake ID
user_qiao_id -- 用户 external ID
instance_qiao_id -- AI external ID
role -- 角色（enum: ConversationRole）
message_type -- 消息类型（enum: ConversationItemMessageType）
text_content -- 文本内容
media_url -- 媒体地址
media_metadata -- 媒体元数据
client_msg_ids -- 客户端消息ID
buffer_id -- 原始缓冲窗口ID
is_excluded_from_context -- 上下文状态（enum: ConversationItemContextStatus）
created_at -- 原始创建时间
archived_at -- 归档时间
```

## ai_request_logs

AI请求日志表，记录所有AI请求和响应（包括生产环境和测试环境）。

```txt
id -- Snowflake ID（attempt 日志ID；当绑定 assistant outbound 消息时作为 llm_request_id）
instance_id -- 关联ai_instances.id
user_id -- 关联users.id
user_qiao_id -- 用户 external ID
style_id -- 关联ai_styles.id
personality_id -- 关联ai_personalities.id
request_type -- 请求类型（enum: AIRequestType）
provider_name -- LLM提供商名称（如doubao, openai, mock等）
model_name -- 使用的模型名称
response_id -- Provider侧响应ID（可为空）
cache_hit -- 是否命中缓存（bool）
request -- 请求内容，JSONB格式
response -- 响应内容，JSONB格式（成功为可用响应；失败为失败片段与诊断上下文）
status -- attempt 状态（enum: AIRequestStatus）
token_count -- 消耗的token数量
response_time -- 当前 attempt 响应时间（毫秒，按 attempt 独立记录）
llm_config_id -- 使用的LLM配置ID
buffer_id -- 关联的 ai_message_buffer.id（同一 buffer 可对应多个 attempt 日志）
created_at -- 请求创建时间
completed_at -- 请求完成时间
```

### ai_request_logs.response.__min_contract

最小契约诊断对象（JSONB 子字段）。

```txt
attempt_index -- 当前 attempt 序号（从 1 开始）
attempt_total -- 配置的总尝试次数
failure_code -- 失败码（成功时可为空）
failure_detail -- 失败详情（可裁剪）
l0_ok -- L0 最小契约是否通过
l1_score_kept -- score 字段是否保留
l1_memory_kept -- memory 字段是否保留
preempted -- 当前 attempt 是否被抢占终止
```

## ai_instance_memories

AI实例记忆表，管理AI对用户的记忆（基于重要性的寿命管理）。

```txt
id -- Snowflake ID
instance_id -- 关联ai_instances.id
instance_qiao_id -- AI external ID
user_id -- 关联users.id
user_qiao_id -- 用户 external ID
memory_type -- 记忆类型（enum: MemoryType）
content -- 记忆内容，简洁的一句话描述
importance -- 重要性1-10，决定寿命（重要性×10=天数）
created_at -- 记忆创建时间
refreshed_at -- AI续期时间，如果有值则从这个时间开始计算寿命
expires_at -- 预计算的过期时间（仅recent类型，通过触发器自动计算，性能优化）
source_message_id -- 触发创建这条记忆的消息ID（溯源用）
status -- 状态（enum: AIInstanceMemoryStatus）
updated_at
```
