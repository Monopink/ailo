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
is_excluded_from_context -- 上下文状态：0=包含，1=排除（默认 0）
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
is_excluded_from_context -- 上下文状态：0=包含，1=排除
created_at -- 原始创建时间
archived_at -- 归档时间
```

## ai_request_logs

AI请求日志表，记录所有AI请求和响应（包括生产环境和测试环境）。

```txt
id -- Snowflake ID
instance_id -- 关联ai_instances.id
user_id -- 关联users.id
user_qiao_id -- 用户 external ID
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

## ai_instance_memories

AI实例记忆表，管理AI对用户的记忆（基于重要性的寿命管理）。

```txt
id -- Snowflake ID
instance_id -- 关联ai_instances.id
instance_qiao_id -- AI external ID
user_id -- 关联users.id
user_qiao_id -- 用户 external ID
memory_type -- 记忆类型：core（核心记忆，永久保留）、recent（近期记忆，会遗忘）
content -- 记忆内容，简洁的一句话描述
importance -- 重要性1-10，决定寿命（重要性×10=天数）
created_at -- 记忆创建时间
refreshed_at -- AI续期时间，如果有值则从这个时间开始计算寿命
expires_at -- 预计算的过期时间（仅recent类型，通过触发器自动计算，性能优化）
source_message_id -- 触发创建这条记忆的消息ID（溯源用）
status -- 状态：1=active（活跃），2=archived（已归档/遗忘）
updated_at
```

**设计说明**：

- **记忆类型**：
  - `memory_type='core'`：核心记忆永久保留，如"用户是程序员"、"我们是好朋友"
  - `memory_type='recent'`：近期记忆会随时间模糊化，如"用户昨天说心情不好"

- **寿命计算**：
  - 公式：`寿命（天）= importance × 10`
  - 示例：importance=1（10天）、importance=5（50天）、importance=10（100天）
  - `expires_at` 字段由数据库触发器自动计算（`COALESCE(refreshed_at, created_at) + importance × 10 days`）

- **模糊化表达**：
  - 系统在prompt中标记模糊程度（不修改content内容）：
    - 75%-100%：[清晰]
    - 50%-75%：[较模糊]
    - 25%-50%：[很模糊]
    - 0%-25%：[极模糊]
  - AI根据标记自然表达不确定性（如"我记得"、"好像"等）

- **AI操作**：
  - `add`：新增记忆
  - `update`：更新记忆内容或重要性（保留创建时间）
  - `refresh`：续期记忆（更新 refreshed_at，重置寿命）
  - `remove`：删除记忆（更新 status = 2）

- **数量限制**：
  - 配置位置：`llm_configs.extra_params.memory_limits` 或 `ai_instances.request_params.memory_limits`
  - 配置格式：`{"core": 30, "recent": 50}`（JSONB）
  - 三级回落：实例层 → LLM配置层 → 代码默认值
  - 执行策略：检索时 limit；写入淘汰暂不实现，后续归档预留见 `docs/tasks/future-features-reserved.md`

- **性能优化**：
  - 使用 `expires_at` 索引快速过滤过期记忆（`WHERE expires_at > NOW()`）
  - 避免运行时计算寿命
- **唯一约束**：
  - `(instance_id, content)` 组合唯一，防止同一个实例出现完全重复的记忆内容，便于 update/remove 通过精确匹配定位记录

- **溯源**：
  - `source_message_id` 记录触发记忆创建的消息ID，用于调试和审计

**相关文档**：
- 规格说明：[../spec/ai/memory-system.md](../spec/ai/memory-system.md)
- 设计文档：[../tasks/completed/ai-memory-system-design.md](../tasks/completed/ai-memory-system-design.md)
