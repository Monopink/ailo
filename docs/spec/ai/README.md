# AI 对话系统

AI 对话系统负责 AI 实例的生命周期管理、关系演进、对话生成和消息发送。

## 文档索引

**实例管理**

- [instance-lifecycle.md](instance-lifecycle.md) - 实例化、状态管理

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

- 用户添加 AI  → [instance-lifecycle.md](instance-lifecycle.md#用户添加流程)
- 用户发送消息 → [conversation-flow.md](conversation-flow.md#消息接收)

系统处理：

- 消息聚合和触发 → [../message/buffer.md](../message/buffer.md)
- 构建 LLM 请求 → [prompt-building.md](prompt-building.md)
- 处理 LLM 响应 → [llm-interaction.md](llm-interaction.md)
- 计算关系分数 → [relationship-system.md](relationship-system.md)
- 发送 AI 消息 → [message-sending.md](message-sending.md)
