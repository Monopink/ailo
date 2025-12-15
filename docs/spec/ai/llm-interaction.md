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

### 配置优先级

LLM 请求参数支持多层级覆盖，优先级从高到低：

1. **函数直接参数** - 调用 `invoke_llm()` 时传入的显式参数
2. **实例级覆盖** - `ai_instances.request_params` 或 `ai_templates.request_params`
3. **配置级默认值** - `llm_configs` 表的专用字段（temperature、max_tokens 等）
4. **配置级扩展参数** - `llm_configs.extra_params`（如 memory_limits）
5. **硬编码默认值** - 代码中的 fallback 值

**示例场景**：

```json
// llm_configs 表
{
  "temperature": 0.7,
  "max_tokens": 4000,
  "extra_params": {"memory_limits": {"core": 30, "recent": 50}}
}

// ai_instances.request_params（实例级覆盖）
{
  "temperature": 0.9,  // 覆盖 llm_configs.temperature
  "memory_limits": {"core": 20, "recent": 40}  // 覆盖 extra_params.memory_limits
}

// 最终生效
{
  "temperature": 0.9,  // 来自实例覆盖
  "max_tokens": 4000,  // 来自配置默认值（未被覆盖）
  "memory_limits": {"core": 20, "recent": 40}  // 来自实例覆盖
}
```

详细的字段说明和用途见：[../../data-dict/llm.md](../../data-dict/llm.md)

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

JSON Schema 存储在 ai_llm_configs.response_format，格式符合 JSON Schema Draft 2020-12 规范。以下为当前标准定义（score 字段会在实例化时根据 style 维度动态展开）：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AI Response Schema with Memory Operations",
  "type": "object",
  "properties": {
    "current_state": {
      "type": "string",
      "description": "根据当前时间、地点等信息推断的状态"
    },
    "internal_thoughts": {
      "type": "string",
      "description": "回复前的内部思考"
    },
    "attack_detected": {
      "type": "boolean",
      "description": "是否检测到攻击/注入意图"
    },
    "should_reply": {"type": "boolean"},
    "should_block": {"type": "boolean"},
    "followup_messages": {
      "type": "array",
      "description": "备发消息数组",
      "items": {"type": "string"}
    },
    "outgoing_messages": {
      "type": "array",
      "description": "立即发送的消息数组",
      "items": {"type": "string"}
    },
    "should_update_memory": {
      "type": "boolean",
      "description": "本轮是否执行记忆操作"
    },
    "memory_operations": {
      "type": "object",
      "description": "remove → update → refresh → add 四类操作的容器，顺序执行",
      "properties": {
        "remove": {
          "type": "array",
          "description": "删除指定 content 的记忆",
          "items": {"type": "string"}
        },
        "update": {
          "type": "array",
          "description": "更正已存在记忆",
          "items": {
            "type": "object",
            "properties": {
              "old_content": {"type": "string"},
              "new_content": {"type": "string"},
              "new_importance": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": ["old_content", "new_content"],
            "additionalProperties": false
          }
        },
        "refresh": {
          "type": "array",
          "description": "续期指定 content 的记忆",
          "items": {"type": "string"}
        },
        "add": {
          "type": "array",
          "description": "新增记忆",
          "items": {
            "type": "object",
            "properties": {
              "memory_type": {"type": "string", "enum": ["core", "recent"]},
              "content": {"type": "string"},
              "importance": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": ["memory_type", "content", "importance"],
            "additionalProperties": false
          }
        }
      },
      "additionalProperties": false
    },
    "score": {
      "type": "object",
      "description": "关系维度分数，字段名与 style 维度一致",
      "properties": {
        "<dimension_name>": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000
        }
      },
      "required": ["<dimension_name>"],
      "additionalProperties": false
    }
  },
  "required": [
    "current_state",
    "attack_detected",
    "should_reply",
    "score",
    "should_update_memory",
    "memory_operations"
  ],
  "additionalProperties": true
}
```

> 注：`score.properties` 会在运行时用真实维度名替换 `<dimension_name>` 占位符，`followup_messages`、`outgoing_messages` 等数组字段可为空。

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

**memory_operations** (object, required)

- 描述：包含 remove/update/refresh/add 四种数组字段的对象，服务端严格按 remove → update → refresh → add 顺序执行
- 处理：只在 `should_update_memory = true` 时读取，任何单项解析失败只记录警告

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

`memory_operations` 是一个对象，包含以下四个数组字段：

- **remove**：字符串数组，表示需要删除（精确匹配 content）的记忆；命中后把记录 `status` 改为 2。
- **update**：对象数组，每项包含 `old_content`、`new_content`、可选 `new_importance`；命中后原地修改同一条记录内容/重要性，保留所有溯源字段。
- **refresh**：字符串数组；命中后仅更新 `refreshed_at`，让数据库触发器重新计算 `expires_at`。
- **add**：对象数组，包含 `memory_type`（core/recent）、`content`、`importance`；若已有同内容的历史记录则复活，否则插入新行。

解析阶段不会更改数据库，真正的写入由 `backend/app/services/ai/memory/operations.py` 负责，且记录无法匹配时会记录 WARNING 继续后续操作。

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
- 实例不再收到用户的消息

**3. memory_operations**

当 `should_update_memory = true` 且四个数组中任一非空时：

- 调用 `process_memory_operations`，按照 remove → update → refresh → add 顺序遍历
- 所有操作都作用于 `ai_instance_memories` 表，字符串字段不再使用
- 单项失败只记录 WARNING，其余操作继续执行

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

**remove**

- 入参：`remove` 数组内的字符串（content）
- 行为：按照 content 精确匹配活跃记忆，把命中记录的 `status` 设为 2，并更新 `updated_at`

**update**

- 入参：数组内对象包含 `old_content`、`new_content`、可选 `new_importance`
- 行为：匹配活跃记忆后直接修改内容/重要性，原地保留 `created_at`、`source_message_id` 等字段；若提供新的 importance，同步重算 expires_at

**refresh**

- 入参：字符串数组
- 行为：匹配活跃 recent/core 记忆后仅更新 `refreshed_at`，依靠触发器将 `expires_at` 滚动

**add**

- 入参：对象数组（`memory_type`、`content`、`importance`）
- 行为：若有同 content 旧记录则复活（重置 `status=1`、`created_at`、`source_message_id`），否则插入新行；`expires_at` 由数据库触发器生成

### 执行顺序

服务端严格按 remove → update → refresh → add 顺序执行。每一类操作会在上一类别完成后的最新数据上运行，并在所有操作结束后一次性 flush。未匹配记录不会中断流程，只会打日志。

### 错误处理

任一操作出现异常会记录 ERROR 并返回 False，由调用方决定是否继续；单个匹配失败仅记录 WARNING，无需人工干预。详见 `backend/app/services/ai/memory/operations.py`。

## 请求日志

### 日志记录

每次 LLM 请求记录到 ai_request_logs 表

记录内容：

- user_id: 关联 users.id
- user_qiao_id: 用户 external ID
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
