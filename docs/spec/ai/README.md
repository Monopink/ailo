# AI 对话系统

AI 对话系统负责 AI 角色的生命周期管理、关系演进、对话生成和消息发送。

## 核心概念

- **AI Persona** - AI 角色原型，定义基础人设和 qiao_id
- **AI Template** - AI 实例模板，定义 LLM 配置和 personality
- **AI Instance** - 用户的 AI 联系人实例，继承 persona 的 qiao_id
- **Relationship** - 关系等级，影响 AI 行为和响应速度
- **Dimension** - 关系维度，多维度分数决定关系等级

## 文档索引

**角色管理**

- [character-lifecycle.md](character-lifecycle.md) - 角色创建、实例化、状态管理

**关系系统**

- [relationship-system.md](relationship-system.md) - 关系分数、位置映射、关系选择

**对话生成**

- [conversation-flow.md](conversation-flow.md) - 完整对话流程
- [prompt-building.md](prompt-building.md) - Prompt 构建、占位符系统
- [llm-interaction.md](llm-interaction.md) - LLM 交互、输出处理

**消息发送**

- [message-sending.md](message-sending.md) - 消息发送、打字模拟、中断处理

## 快速查找

**按场景索引**

用户操作：

- 用户添加 AI 角色 → [character-lifecycle.md](character-lifecycle.md#用户添加流程)
- 用户发送消息 → [conversation-flow.md](conversation-flow.md#消息接收)

系统处理：

- 消息聚合和触发 → [../message/buffer.md](../message/buffer.md)
- 构建 LLM 请求 → [prompt-building.md](prompt-building.md)
- 处理 LLM 响应 → [llm-interaction.md](llm-interaction.md)
- 计算关系分数 → [relationship-system.md](relationship-system.md)
- 发送 AI 消息 → [message-sending.md](message-sending.md)

## 依赖关系

AI 对话系统依赖以下基础设施：

- [../message/](../message/) - 消息传输、缓冲、存储
- [../contact/](../contact/) - 联系人管理
- [../../data-dict/ai-*.md](../../data-dict/) - 数据表结构
- [../../api/ai-*.md](../../api/) - API 接口定义

## 数据流概览

```
用户发送消息
  ↓
消息缓冲聚合 (message/buffer.md)
  ↓
触发 LLM 处理
  ↓
构建 Prompt (prompt-building.md)
  ↓
调用 LLM (llm-interaction.md)
  ↓
处理响应 (llm-interaction.md)
  ↓
更新关系分数 (relationship-system.md)
  ↓
发送消息 (message-sending.md)
  ↓
用户收到消息
```

## 关键配置

从 system_configs 表获取的配置项：

**消息缓冲**（详见 [../message/buffer.md](../message/buffer.md)）

- message_buffer_normal_wait_ms
- message_buffer_typing_total_wait_ms

**关系系统**（详见 [relationship-system.md](relationship-system.md)）

- 位置映射参数存储在 ai_instance_dimensions.position_mapping_params

**消息发送**（详见 [message-sending.md](message-sending.md)）

- 打字速度存储在 ai_instances.typing_speed_wpm
- followup_delay_ms 存储在 ai_relationships 表
