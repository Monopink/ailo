# Prompt 构建

本文档说明如何构建 LLM 请求的 system prompt 和 context。

## 数据模型

**数据表定义** 详见：

- [../../data-dict/ai-configuration.md](../../data-dict/ai-configuration.md)
- [../../data-dict/ai-instantiation.md](../../data-dict/ai-instantiation.md)
- [../../data-dict/ai-conversation.md](../../data-dict/ai-conversation.md)

## 核心概念

### Personality

人格提示词模板，定义 AI 的基础性格和行为规则。

**职责**：

- 定义 prompt 模板（包含占位符）
- 模板中使用 {{variable_name}} 语法

### Prompt Variables

实例特定的占位符变量。

**存储位置**：ai_instances.prompt_variables（JSON 对象）

**用途**：为 personality 模板提供实例特定的值

### System Placeholders

系统预设的占位符，优先级高于实例变量。

**冲突处理**：如果实例变量与系统占位符同名，系统占位符优先

## Prompt 构建流程

### 流程概述

```
获取 personality.prompt 模板
  ↓
替换系统占位符
  ↓
替换实例占位符
  ↓
检测未知占位符
  ↓
清空未知占位符
  ↓
构建 context
  ↓
合并为完整 LLM 请求
```

### 步骤 1：获取模板

输入：instance.template_id

查询：ai_templates → ai_personalities

输出：personality.prompt（包含占位符的模板）

### 步骤 2：替换系统占位符

按顺序替换以下占位符：

**{{relationship_prompt}}**

- 来源：ai_relationships.prompt_fragment
- 查询：通过 ai_instance_dimensions 获取当前 relationship_id
- 如果 relationship_id = NULL：内容为空字符串

**{{score:dimension_name}}**

- 来源：ai_instance_dimensions.position
- 逻辑：通过位置映射算法反向计算得出 score
- dimension_name：ai_style_dimensions.name
- 详见：[relationship-system.md](relationship-system.md#反向计算)

**{{self_profile}}**

- 来源：`instance_context.profile`（由实例上下文加载阶段提供）
- 正常查询条件：owner_qiao_id = instance.qiao_id AND owner_type IN (2, 3)
- 内容：profile 的文本描述
- 缺失处理：profile 缺失时置空字符串，不中断对话处理，并记录告警日志

**{{other_profile}}**

- 来源：profiles 表 + user_profile_logs 表
- 查询条件：owner_qiao_id = user_qiao_id AND owner_type = 1
- 内容：用户 profile 的文本描述 + 近期修改内容描述

**{{current_datetime}}**

- 来源：系统时间（+8:00 时区）
- 格式：日期、农历、时间
- 示例：2024年11月23日 星期六 农历十月廿三 14:30

**{{memory}}**

- 来源：`ai_instance_memories`，通过 `backend/app/services/ai/memory/retrieval.py:build_memory_prompt` 查询
- 逻辑：根据 `memory/config.py` 的回落顺序读取 core/recent 限额，过滤 `status=1`（recent 额外要求未过期），按重要性与创建时间排序
- 输出：带 `[清晰]/[较模糊]/[很模糊]/[极模糊]` 标签的 Markdown 列表，无匹配记录则输出空字符串

**{{pending_messages}}**

- 来源：ai_conversation_state.pending_messages
- 条件：上一次发送被打断
- 内容：pending_messages.outgoing 的文本列表描述
- 用途：提示 LLM 需要优先处理这些文本
- 详见：[message-sending.md](message-sending.md#中断处理)

### 步骤 3：替换实例占位符

输入：ai_instances.prompt_variables（JSON 对象）

逻辑：遍历所有键值对，替换模板中的 {{key}}

注意：如果与系统占位符冲突，此步骤不会覆盖（系统占位符已替换）

### 步骤 4：检测未知占位符

使用正则表达式检测所有剩余的 {{...}} 占位符

正则：`\\{\\{([^}]+)\\}\\}`

输出：未知占位符列表

### 步骤 5：处理未知占位符

如果存在未知占位符：

- 记录 WARNING 日志
- 日志包含：未知占位符列表、模板预览
- 自动清空所有未知占位符（替换为空字符串）

目的：确保最终 prompt 不包含任何未替换的占位符

### 步骤 6：构建 context

详见下文"Context 构建"章节（此阶段已包含记忆占位符生成，context 仅指会话历史）

### 步骤 7：合并为完整请求

结构：

```
messages = [
  {role: "system", content: [替换后的 prompt]},
  ...context_messages
]
```

## Context 构建

### 数据来源

从 ai_conversation_items 查询对话历史

详见：[../message/context.md](../message/context.md)

### 查询条件

- user_qiao_id = 当前用户
- instance_qiao_id = 当前实例
- is_excluded_from_context = 0（排除攻击消息）
- 按 created_at 排序
- 限制数量（默认最近 20 条）

### 消息格式

ai_conversation_items 采用扁平字段存储（message_type / text_content / media_url / media_metadata）。构造 LLM 请求时，builder 会根据 message_type 重新拼装为 Doubao Responses API 兼容的数组：

```
[
  {type: "text", text: "[今天17:19] 你好"},
  {type: "image_url", image_url: {url: "...", detail: "high"}}
]
```

目前仅支持 text / image / audio 三种类型；图片与音频的元数据存放在 media_metadata，转换时一并带入。

### 时间标记&消息合并

见 [../message/context.md](../message/context.md#时间标记格式化)

### Token 限制

根据 LLM 上下文窗口动态裁剪

策略：

- 从最新消息开始累计 token
- 超过限制时停止添加更早的消息
- 保留 system prompt 的 token 预算

实现位置：`backend/app/services/ai/conversation_prompt.py`（`build_conversation_context`）

配置来源：system_configs.ai_context_max_messages（默认 20）

## 攻击消息处理

### 检测机制

LLM 输出 attack_detected = true 时触发

详见：[llm-interaction.md](llm-interaction.md#attack_detected)

### 处理逻辑

更新该 buffer 关联的所有用户消息：

- 设置 is_excluded_from_context = 1

效果：

- 后续查询自动跳过这些消息
- 内容仍完整保存用于审计
- 不污染上下文

详见：[../message/context.md](../message/context.md#排除攻击消息)

## 占位符优先级

优先级从高到低：

1. 系统占位符（固定逻辑）
2. 实例占位符（ai_instances.prompt_variables）
3. 未知占位符（自动清空）

## 错误处理

### 占位符值转换失败

如果占位符值转换失败（如类型错误）：

- 清空该占位符（替换为空字符串）
- 记录 WARNING 日志

### 未知占位符

如果存在未知占位符：

- 记录 WARNING 日志
- 自动清空
- 不中断流程

### 数据查询失败

如果查询 profile、relationship 等数据失败：

- 对应占位符使用空字符串
- 记录 ERROR 日志
- 继续构建 prompt

补充：`self_profile` 的 profile 缺失属于可降级场景，记录 WARNING 日志并继续。
