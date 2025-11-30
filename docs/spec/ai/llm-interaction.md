# LLM 交互

本文档说明 LLM 请求、响应处理和输出验证。

## 数据模型

**数据表定义** 详见：

- [../../data-dict/ai-llm-configs.md](../../data-dict/ai-llm-configs.md)
- [../../data-dict/ai-request-logs.md](../../data-dict/ai-request-logs.md)

## 核心概念

### LLM Config

LLM 配置，定义模型参数和 JSON Schema。

**职责**：

- 定义 provider 和 model
- 定义 temperature、max_tokens 等参数
- 定义 response_format（JSON Schema）

### JSON Schema

约束 LLM 输出格式的 schema。

**职责**：

- 定义输出字段和类型
- 定义必填字段
- 定义字段约束（如 enum、minimum、maximum）

**重要**：JSON Schema 可以自由增减字段，系统只处理名称匹配的字段

## LLM 请求流程

### 流程概述

```
构建 Prompt (prompt-building.md)
  ↓
获取 LLM Config
  ↓
发起流式请求
  ↓
监听抢占信号
  ↓
接收响应
  ↓
验证 JSON Schema
  ↓
处理响应 (process_llm_response)
```

### 步骤 1：构建 Prompt

详见：[prompt-building.md](prompt-building.md)

输出：完整的 messages 数组

### 步骤 2：获取 LLM Config

输入：instance.template_id

查询：ai_templates → ai_llm_configs

输出：llm_config 记录（包含 response_format）

### 步骤 3：发起流式请求

使用 Doubao Responses API（兼容 OpenAI SDK）

请求参数：

- model: llm_config.model
- messages: 构建的 messages
- temperature: llm_config.temperature
- max_tokens: llm_config.max_tokens
- response_format: llm_config.response_format
- stream: true

### 步骤 4：监听抢占信号

在流式读取过程中，检查是否有新窗口抢占

抢占条件：

- 同会话有新的 LOCKED buffer
- 当前 buffer 状态变为 CANCELLED

抢占处理：

- 立即停止读取流式输出
- 丢弃当前结果
- 减少后续输出 tokens 费用

详见：[../message/buffer.md](../message/buffer.md#并发处理)

### 步骤 5：接收响应

累积流式输出，直到完成或被抢占

输出：完整的 JSON 字符串

### 步骤 6：验证 JSON Schema

使用 llm_config.response_format 验证输出

验证失败：

- 记录 ERROR 日志
- 丢弃结果
- 不更新任何状态

验证成功：

- 解析为 JSON 对象
- 进入响应处理流程

### 步骤 7：处理响应

调用 process_llm_response 函数

详见下文"响应处理"章节

## JSON Schema 定义

### Schema 结构

JSON Schema 存储在 ai_llm_configs.response_format

格式：符合 JSON Schema Draft 2020-12 规范

### 标准字段

系统识别并处理以下字段（其他字段忽略）：

**current_state** (string)

- 描述：AI 当前的状态（地点、正在做的事、心情）
- 处理：暂不处理，预留未来功能

**internal_thoughts** (string)

- 描述：AI 的内心思考
- 处理：不处理，仅供 LLM 推理

**attack_detected** (boolean, required)

- 描述：是否检测到攻击或注入意图
- 处理：标记攻击消息，排除上下文

**should_reply** (boolean, required)

- 描述：是否要回复用户
- 处理：控制是否发送消息

**outgoing_messages** (array of string)

- 描述：要发送的消息数组
- 处理：按顺序发送

**score** (object, required)

- 描述：关系维度分数
- 格式：{dimension_name: integer}
- 处理：更新 ai_instance_dimensions

**followup_messages** (array of string)

- 描述：延迟发送的消息数组
- 处理：等待 followup_delay_ms 后发送

**should_block** (boolean)

- 描述：是否删除好友
- 处理：更新 ai_instances.status = blocked

**should_update_memory** (boolean, required)

- 描述：是否更新记忆
- 处理：控制是否执行 memory_operations

**memory_operations** (array, required)

- 描述：记忆操作列表
- 处理：顺序执行记忆操作

### Score 字段约束

score 对象的字段必须与 ai_style_dimensions 一致

每个维度必须定义：

- type: integer
- minimum: 最小值
- maximum: 最大值

示例：

```
"score": {
  "type": "object",
  "properties": {
    "intimacy": {
      "type": "integer",
      "minimum": 0,
      "maximum": 1000
    },
    "trust": {
      "type": "integer",
      "minimum": 0,
      "maximum": 1000
    }
  },
  "required": ["intimacy", "trust"]
}
```

### Memory Operations 结构

每个操作包含：

**operation** (enum: add/replace/delete, required)

- 操作类型

**content** (string)

- 新增或替换的内容
- add 和 replace 时必填

**target_text** (string)

- 要匹配的旧文本
- replace 和 delete 时必填

**insert_position** (string)

- 插入位置
- add 时有效
- 可选值：start / end / after:<text> / before:<text>

## 响应处理

### 处理函数

函数：process_llm_response

输入：

- LLM 输出的 JSON 对象
- buffer_id
- instance
- user

输出：无（副作用：更新数据库、发送消息）

### 处理顺序

按以下顺序处理各个字段：

**1. attack_detected**

如果为 true：

- 更新该 buffer 关联的所有用户消息
- 设置 is_excluded_from_context = true
- 记录 user_violation_logs

详见：[prompt-building.md](prompt-building.md#攻击消息处理)

**2. should_block**

如果为 true：

- 更新 ai_instances.status = 2 (blocked)
- 用户无法再给该角色发消息

**3. memory_operations**

如果 should_update_memory = true：

- 顺序执行 memory_operations 数组
- 每条操作在前一条操作修改后的记忆上执行
- 更新 ai_instances.memory

详见下文"记忆操作"章节

**4. score**

更新关系分数：

- 调用关系系统计算新的 position 和 relationship
- 更新 ai_instance_dimensions
- 更新 ai_instances.relationship_counts（如果关系变更）

详见：[relationship-system.md](relationship-system.md#分数计算和关系选择)

**5. 消息发送**

如果 should_reply = true：

- 调用 send_ai_messages_with_typing 异步发送消息
- 发送 outgoing_messages
- 延迟后发送 followup_messages

详见：[message-sending.md](message-sending.md)

## 记忆操作

### 操作类型

**add** - 添加新内容

参数：

- content: 要添加的内容
- insert_position: 插入位置

逻辑：

- start: 插入到开头
- end: 插入到末尾
- after:<text>: 插入到指定文本之后
- before:<text>: 插入到指定文本之前

**replace** - 替换内容

参数：

- target_text: 要替换的文本
- content: 新内容

逻辑：

- 查找 target_text
- 替换为 content
- 如果找不到，记录 WARNING 日志

**delete** - 删除内容

参数：

- target_text: 要删除的文本

逻辑：

- 查找 target_text
- 删除该文本
- 如果找不到，记录 WARNING 日志

### 执行顺序

memory_operations 数组按顺序执行

每条操作在前一条操作修改后的记忆上执行

示例：

```
初始 memory: "用户喜欢猫。用户正在准备去旅行。"

操作 1 (add, end): "用户今天告诉我他很喜欢猫。"
结果: "用户喜欢猫。用户正在准备去旅行。用户今天告诉我他很喜欢猫。"

操作 2 (replace): "用户正在准备去旅行" → "用户已经到达泰国旅行中"
结果: "用户喜欢猫。用户已经到达泰国旅行中。用户今天告诉我他很喜欢猫。"

操作 3 (delete): "用户喜欢猫。"
结果: "用户已经到达泰国旅行中。用户今天告诉我他很喜欢猫。"
```

### 错误处理

如果操作失败（如找不到 target_text）：

- 记录 WARNING 日志
- 跳过该操作
- 继续执行后续操作

## 请求日志

### 日志记录

每次 LLM 请求记录到 ai_request_logs 表

记录内容：

- buffer_id: 关联的 buffer
- llm_config_id: 使用的 LLM 配置
- response_id: Doubao 返回的 response_id
- prompt_tokens: 输入 token 数
- completion_tokens: 输出 token 数
- total_tokens: 总 token 数
- request_time_ms: 请求耗时（毫秒）
- created_at: 请求时间

### 查询日志

通过 buffer_id 关联查询：

```
查询条件：
- ai_request_logs.buffer_id = 目标 buffer_id

输出：
- LLM 配置
- Token 使用量
- 请求耗时
- 响应 ID
```

## 错误处理

### JSON Schema 验证失败

触发条件：

- LLM 输出不符合 response_format
- 缺少必填字段
- 字段类型错误

处理方式：

- 记录 ERROR 日志
- 丢弃结果
- 不更新任何状态
- 不发送消息

### 流式请求失败

触发条件：

- 网络错误
- API 错误
- 超时

处理方式：

- 记录 ERROR 日志
- 重试（可选，根据错误类型）
- 如果最终失败，不更新状态

### 被抢占

触发条件：

- 新窗口抢占
- buffer 状态变为 CANCELLED

处理方式：

- 立即停止读取
- 丢弃结果
- 不记录日志（正常行为）

### 响应处理失败

触发条件：

- 数据库更新失败
- 关系计算失败
- 记忆操作失败

处理方式：

- 记录 ERROR 日志
- 部分失败：跳过失败的操作，继续处理其他操作
- 完全失败：回滚事务，不更新任何状态

## 实现位置

- LLM 请求：backend/app/services/ai/llm/client.py
- 响应处理：backend/app/services/ai/llm/response_processor.py
- 记忆操作：backend/app/services/ai/memory/operations.py
- JSON Schema 验证：backend/app/services/ai/llm/validator.py
