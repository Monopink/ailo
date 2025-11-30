# 消息发送

本文档说明 AI 消息的发送、打字模拟和中断处理。

## 数据模型

**数据表定义** 详见：

- [../../data-dict/ai-conversation-state.md](../../data-dict/ai-conversation-state.md)
- [../../data-dict/ai-conversation-items.md](../../data-dict/ai-conversation-items.md)
- [../../data-dict/message-delivery-failures.md](../../data-dict/message-delivery-failures.md)

## 核心概念

### 消息类型

**outgoing_messages**

- 立即发送的消息
- 按顺序逐条发送
- 每条消息模拟打字延迟

**followup_messages**

- 延迟发送的消息
- 在 outgoing_messages 发送完成后等待 followup_delay_ms
- 按顺序逐条发送

### 打字模拟

模拟真人打字速度，增强拟人化体验。

**参数来源**：ai_instances.typing_speed_wpm（词/分钟）

**计算逻辑**：详见下文"打字速度计算"章节

### 中断机制

用户发送新消息时，中断当前发送任务。

**未发送内容**：写入 ai_conversation_state.pending_messages

**下次处理**：通过 {{pending_messages}} 占位符提示 LLM

## 消息发送流程

### 流程概述

```
process_llm_response 调用 send_ai_messages_with_typing
  ↓
启动异步发送任务
  ↓
发送 outgoing_messages（逐条）
  ↓
等待 followup_delay_ms
  ↓
发送 followup_messages（逐条）
  ↓
清空 ai_conversation_state
```

### 步骤 1：启动异步任务

调用位置：process_llm_response 处理完 LLM 响应后

输入：

- instance
- user
- outgoing_messages
- followup_messages
- buffer_id

输出：异步任务 ID

### 步骤 2：发送 outgoing_messages

对每条消息：

- 计算打字延迟时间
- 等待延迟时间
- 检查是否被中断
- 如果未中断，发送消息
- 写入 ai_conversation_items

详见下文"单条消息发送"章节

### 步骤 3：等待 followup_delay_ms

获取延迟时间：

- 查询 ai_instance_dimensions 获取当前 relationship_id
- 查询 ai_relationships.followup_delay_ms

等待期间：

- 检查是否被中断
- 如果被中断，停止发送

### 步骤 4：发送 followup_messages

逻辑同 outgoing_messages

### 步骤 5：清空状态

如果全部发送成功：

- 清空 ai_conversation_state.pending_messages
- 清空 ai_conversation_state.sending_task_id

如果被中断：

- 保留 pending_messages（未发送的消息）
- 清空 sending_task_id

## 单条消息发送

### 流程

```
计算打字延迟
  ↓
等待延迟时间
  ↓
检查中断信号
  ↓
调用 LeanCloud API 发送
  ↓
写入 ai_conversation_items
  ↓
处理发送失败
```

### 步骤 1：计算打字延迟

输入：消息文本

计算：详见下文"打字速度计算"章节

输出：延迟时间（毫秒）

### 步骤 2：等待延迟时间

使用异步 sleep，等待计算出的延迟时间

等待期间：

- 定期检查中断信号
- 如果被中断，立即返回

### 步骤 3：检查中断信号

中断条件：

- 用户发送新消息（创建新的 OPEN buffer）
- ai_conversation_state.sending_task_id 被清空

如果被中断：

- 停止发送
- 将未发送的消息写入 pending_messages
- 返回

### 步骤 4：发送消息

调用 LeanCloud REST API 发送消息

详见：[../message/leancloud.md](../message/leancloud.md)

参数：

- conversation_id: 系统对话 ID
- from_peer: instance.qiao_id
- message: 消息内容
- transient: false

### 步骤 5：写入 ai_conversation_items

发送成功后立即写入：

- role = "assistant"
- content = 消息内容（JSONB 格式）
- buffer_id = 触发的 buffer_id
- created_at = 当前时间（真实发送时间）

注意：每条消息独立插入，不批量插入

### 步骤 6：处理发送失败

如果 LeanCloud API 调用失败：

- 写入 message_delivery_failures 表
- 记录失败原因
- 将失败的消息写入 pending_messages
- 停止后续发送

详见：[../message/failure-handling.md](../message/failure-handling.md)

## 打字速度计算

### 参数

**typing_speed_wpm**

- 来源：ai_instances.typing_speed_wpm
- 单位：词/分钟（Words Per Minute）
- 默认值：35 WPM（如果配置缺失或 <= 0）

### 词数计算规则

1 词 = 以下任一：

- 1 个全角字符（中文、日文等）
- 3 个半角字符（英文、数字等）
- 1 个 emoji
- 1 个特殊字符

### 计算公式

```
秒/词 = 60 / typing_speed_wpm
总耗时（秒）= 秒/词 * 词数
总耗时（毫秒）= 总耗时（秒）* 1000
```

### 示例

消息："你好，今天天气不错！😊"

词数计算：

- "你好，今天天气不错！" = 10 个全角字符 = 10 词
- "😊" = 1 个 emoji = 1 词
- 总计：11 词

打字速度：35 WPM

计算：

- 秒/词 = 60 / 35 ≈ 1.71 秒
- 总耗时 = 1.71 * 11 ≈ 18.86 秒
- 总耗时（毫秒）= 18860 毫秒

### 边界处理

如果 typing_speed_wpm <= 0 或 NULL：

- 使用默认值 35 WPM
- 记录 WARNING 日志

如果消息为空：

- 延迟时间 = 0
- 不发送消息

## 中断处理

### 中断触发

**触发条件**：

- 用户发送新消息
- 创建新的 OPEN buffer

**检测机制**：

- 查询 ai_message_buffer
- 条件：user_qiao_id + instance_qiao_id
- 条件：aggregate_state = 1 (OPEN)
- 条件：created_at > 当前任务开始时间

### 中断逻辑

**步骤 1：停止发送**

立即停止当前发送任务：

- 取消等待中的延迟
- 不发送后续消息

**步骤 2：记录未发送消息**

将未发送的消息写入 ai_conversation_state.pending_messages：

- 包括 outgoing_messages 中未发送的
- 包括 followup_messages 中未发送的
- 按原顺序保存

**步骤 3：清空任务 ID**

清空 ai_conversation_state.sending_task_id

### 下次处理

**触发时机**：下次 LLM 请求时

**处理逻辑**：

- 通过 {{pending_messages}} 占位符提示 LLM
- LLM 决定如何处理这些未发送的消息
- 可能的决策：
  - 继续发送原消息
  - 修改后发送
  - 放弃发送

详见：[prompt-building.md](prompt-building.md#系统占位符)

### 特殊情况

**should_reply = false**

如果 LLM 输出 should_reply = false：

- 清空 ai_conversation_state.pending_messages
- 清空 ai_conversation_state.sending_task_id
- 不发送任何消息

**目的**：LLM 主动决定不回复，清空待发消息

## 发送失败处理

### 失败类型

**网络错误**

- 超时
- 连接失败
- DNS 解析失败

**API 错误**

- 4xx 错误（客户端错误）
- 5xx 错误（服务端错误）
- 认证失败

**业务错误**

- 对话不存在
- 用户被封禁
- 消息格式错误

### 处理策略

**步骤 1：记录失败**

写入 message_delivery_failures 表：

- msg_id_server: 服务端消息 ID
- failure_reason: 失败原因
- retry_count: 重试次数（初始为 0）
- next_retry_at: 下次重试时间
- created_at: 失败时间

**步骤 2：写入 pending_messages**

将失败的消息写入 ai_conversation_state.pending_messages

**步骤 3：停止后续发送**

不再发送后续的 outgoing_messages 和 followup_messages

**步骤 4：重试（可选）**

根据失败类型决定是否重试：

- 网络错误：重试
- 5xx 错误：重试
- 4xx 错误：不重试
- 业务错误：不重试

重试策略：

- 指数退避（1s, 2s, 4s, 8s, ...）
- 最大重试次数：3 次
- 超过最大次数：放弃重试

详见：[../message/failure-handling.md](../message/failure-handling.md)

## 状态管理

### ai_conversation_state 表

**字段**：

- pending_messages: 未发送的消息列表（JSON 数组）
- sending_task_id: 当前发送任务 ID
- last_buffer_id: 最后一次触发的 buffer_id

**用途**：

- 跟踪发送状态
- 支持中断和恢复
- 避免重复发送

### 状态转换

```
空闲
  ↓ (开始发送)
发送中 (sending_task_id 非空)
  ↓ (全部发送成功)
空闲 (清空 pending_messages 和 sending_task_id)

发送中
  ↓ (被中断)
待恢复 (pending_messages 非空, sending_task_id 为空)
  ↓ (下次 LLM 请求)
空闲 (LLM 决定如何处理)
```

## 并发控制

### 同会话串行

同一会话（user + instance）的发送任务串行执行：

- 同时只有一个发送任务
- 新任务启动时，中断旧任务

### 跨会话并行

不同会话的发送任务并行执行：

- 互不影响
- 独立的状态管理

## 实现位置

- 消息发送：backend/app/services/ai/message/sender.py
- 打字速度计算：backend/app/services/ai/message/typing.py
- 中断处理：backend/app/services/ai/message/interruption.py
- 状态管理：backend/app/services/ai/conversation/state.py
