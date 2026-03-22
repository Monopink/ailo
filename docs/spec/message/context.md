# 上下文管理

本文档说明 AI 如何查询和构建对话上下文。

- ai_conversation_items 只存储消息内容，不管理状态
- 通过 is_excluded_from_context = 1 标记攻击消息
- 上下文查询时自动排除攻击消息
- converter 层负责格式转换和消息合并

## ai_conversation_items 表

完整表结构见 [data-dict/ai-conversation.md](../../data-dict/ai-conversation.md)

### 消息存储格式

ai_conversation_items 使用扁平字段存储（message_type/text_content/media_url/media_metadata），转换为 LLM 请求格式由 converter 在构建阶段完成，详见 `../ai/prompt-building.md` 与 `backend/app/services/ai/context/converter.py`。

## 上下文查询

### 基本查询

从 ai_conversation_items 查询对话历史，自动排除攻击消息

### 查询策略

- 最近 N 条 - 默认查询最近 20 条消息
- Token 限制 - 根据 LLM 上下文窗口动态裁剪
- 时间窗口 - 可选：只查询最近 N 天的消息

### 排除攻击消息

当 LLM 检测到攻击消息时，标记 is_excluded_from_context = 1。

**逻辑**：

更新触发该请求的用户消息记录，设置 is_excluded_from_context = 1。

后续查询会自动跳过这些消息，但内容仍完整保存用于审计。

## 时间标记格式化

### _format_time_prefix 函数

在构造 LLM 消息时生成人性化时间前缀，数据库中仅保留原始文本。

**格式规则**：

- 今天 → `今天HH:MM` - 示例：`今天17:19`
- 昨天 → `昨天HH:MM` - 示例：`昨天09:30`
- 本周 → `周X HH:MM` - 示例：`周三 14:25`
- 本年 → `MM-DD(X天前) HH:MM` - 示例：`11-18(五天前) 17:19`
- 去年及更早 → `YYYY-MM-DD HH:MM` - 示例：`2023-12-25 10:00`

**实现位置**：`backend/app/services/ai/context/converter.py`

**示例**：

原始消息：

```json
{
  "role": "user",
  "message_type": "text",
  "text_content": "你好",
  "created_at": "2024-11-18T17:19:00"
}
```

添加时间前缀后：

```json
{
  "role": "user",
  "message_type": "text",
  "text_content": "[11-18(五天前) 17:19] 你好"
}
```

## Converter 层消息合并

### 设计原理

LLM 要求连续同 role 的消息必须合并，converter 层负责此逻辑。

### 合并规则

**合并条件**：

- 连续的消息
- 相同的 role
- 都是 text 类型

**合并方式**：

- 使用 `\n\n` 分隔
- 保留每条消息的时间前缀

**示例**：

原始消息：

```json
[
  {"role": "user", "content": [{"type": "text", "text": "[今天17:19] 你好"}]},
  {"role": "user", "content": [{"type": "text", "text": "[今天17:20] 在吗"}]}
]
```

合并后：

```json
[
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "[今天17:19] 你好\n\n[今天17:20] 在吗"
      }
    ]
  }
]
```

### 不合并的情况

- 不同 role 的消息
- 包含非 text 类型的消息（图片、视频等）
- 中间插入了 system 消息

## 与 buffer_id 的关联

### 关联关系

每条 ai_conversation_items 记录通过 buffer_id 关联到触发此次 LLM 请求的 buffer 窗口。

**用途**：

- 追溯消息来源
- 关联 LLM 请求日志（通过 buffer_id 查询 ai_request_logs）
- 调试和审计

### LLM 元数据存储

LLM 请求的元数据（llm_config_id、response_id、token 使用量等）存储在 ai_request_logs 表中，通过 buffer_id 关联查询。

## 上下文裁剪策略

### Token 限制

根据 LLM 上下文窗口动态裁剪：

1. 从最新消息开始累计 token
2. 超过限制时停止添加更早的消息
3. 保留 system prompt 的 token 预算

**实现位置**：`backend/app/services/ai/context/builder.py`

### 时间窗口

可选配置：只查询最近 N 天的消息。

从 system_configs 获取 `ai_context_time_window_days`（默认 30 天）。

### 消息数量限制

默认查询最近 20 条消息，可通过配置调整。

从 system_configs 获取 `ai_context_max_messages`（默认 20）。

## 消息写入时机

### 用户消息

用户消息在 buffer 聚合时立即写入 ai_conversation_items。

**逻辑步骤**：

1. 创建或更新 buffer 窗口
2. 同时写入 ai_conversation_items
3. 设置 role = "user"
4. 设置 buffer_id 关联
5. 设置 is_excluded_from_context = 0

### Assistant 消息

Assistant 消息在实际发送时写入（不是在 buffer 完成时）。

**逻辑步骤**：

1. Buffer 标记为 COMPLETE
2. 调用 send_ai_messages_with_typing 发送消息
3. 每发送一条消息，立即插入 ai_conversation_items
4. 设置 role = "assistant"
5. 设置 buffer_id 关联
6. 记录真实发送时间（created_at）

详见 spec/ai/message-sending.md
