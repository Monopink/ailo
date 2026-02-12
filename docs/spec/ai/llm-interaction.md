# LLM 交互

本文档只记录 LLM 调用链路的规则与边界，不重复字段字典和子系统实现细节。

## 职责边界

- 本文档：请求参数合并、流式调用、抢占、Schema 校验闸门、请求追踪，输出字段契约。
- 端到端编排：见 [conversation-flow.md](conversation-flow.md)。
- 字段定义：见 [../../data-dict/llm.md](../../data-dict/llm.md) 与 [../../data-dict/ai-conversation.md](../../data-dict/ai-conversation.md#ai_request_logs)。

## 配置来源与优先级

LLM 请求参数允许多层覆盖，优先级从高到低：

1. 调用 `invoke_llm()` 时显式传入参数
2. `ai_instances.request_params` 或 `ai_templates.request_params`
3. `llm_configs` 的专用字段（例如 `temperature`、`max_tokens`）
4. `llm_configs.extra_params` 的扩展字段（例如 `memory_limits`）

约束：

- 影响行为的关键参数必须可追溯到配置来源。
- 禁止新增“静默回退”掩盖配置错误。

## 调用流程

```
构建 Prompt（prompt-building.md）
  ↓
选择 LLM 配置（llm_configs）
  ↓
发起请求（流式或非流式）
  ↓
监听抢占信号
  ↓
接收完整响应
  ↓
按 response_format 做 JSON Schema 校验
  ↓
进入响应处理
```

流程要点：

- 检测到 `active_turn_version` 切换时，当前请求必须中止并丢弃结果。
- 仅 Schema 校验通过的响应才允许进入后续处理。
- 响应返回后、副作用执行前必须再次执行抢占校验。
- 抢占是并发控制的正常路径，不属于业务异常。

## 响应处理

LLM 响应的字段语义、处理顺序和跨模块归属见本文档的“系统识别字段”和“处理顺序”章节。

## 请求追踪与日志

为保证可审计性，调用链路必须满足：

- 每次调用都具备 `llm_request_id`，并与 `ai_request_logs.id` 一一对应。
- `ai_request_logs` 的写入入口保持唯一（`conversation_flow` 层）。
- `request` / `response` 保存完整载荷与原始响应（JSONB），敏感字段必须脱敏。

字段清单与类型以 data-dict 为准：

- [../../data-dict/ai-conversation.md#ai_request_logs](../../data-dict/ai-conversation.md#ai_request_logs)

## 错误边界

- 调用失败（网络、Provider、超时）：记录 ERROR，由编排层决定重试与状态推进。
- Schema 校验失败：丢弃结果，不进入响应处理。
- 抢占：`active_turn_version` 切换后立即中断并丢弃结果，按正常并发路径处理。
- finalize 失败：按抢占路径处理，不进入发送与会话副作用。
- 响应处理失败：由响应处理模块按字段级/事务级规则处理并记录日志。

## Schema 约束

- Schema 来源：`llm_configs.response_format`。
- 规范版本：JSON Schema Draft 2020-12。
- `score` 维度在运行时由 style 维度动态展开（维度名来自 `ai_style_dimensions`）。
- 可扩展字段允许存在，但系统仅处理已登记字段；未知字段忽略。

## 系统识别字段

### current_state

- 类型：string
- 语义：角色当前状态补充
- 处理：当前不落库，保留为扩展位

### internal_thoughts

- 类型：string
- 语义：回复前内部思考
- 处理：不参与业务状态更新

### attack_detected

- 类型：boolean
- 语义：是否判定本轮存在攻击/注入意图
- 处理归属：攻击消息标记与上下文排除（见 [prompt-building.md](prompt-building.md#攻击消息处理)）

### should_block

- 类型：boolean
- 语义：是否将实例转为屏蔽状态
- 处理归属：实例状态更新

### should_reply

- 类型：boolean
- 语义：是否发送回复
- 处理归属：消息发送开关（见 [message-sending.md](message-sending.md)）

### outgoing_messages

- 类型：string[]
- 语义：立即发送消息序列
- 处理归属：按顺序发送

### followup_messages

- 类型：string[]
- 语义：延迟发送消息序列
- 处理归属：在延迟后逐条发送

### should_update_memory

- 类型：boolean
- 语义：是否执行记忆写入
- 处理归属：记忆操作开关

### memory_operations

- 类型：object
- 语义：记忆操作容器（`remove` / `update` / `refresh` / `add`）
- 处理归属：见 [memory-system.md](memory-system.md#记忆操作协议)

### score

- 类型：object（`{dimension_name: int}`）
- 语义：关系维度分数
- 处理归属：关系系统更新（见 [relationship-system.md](relationship-system.md)）

## 处理顺序

响应处理按以下固定顺序执行：

1. `attack_detected`
2. `should_block`
3. 消息发送（受 `should_reply`、`outgoing_messages`、`followup_messages` 控制）
4. 首条发送门槛检查（首条 assistant 消息发送成功且落库成功）
5. `memory_operations`（仅当 `should_update_memory=true`，且门槛已达成）
6. `score`（且门槛已达成）

顺序约束用于避免跨模块副作用冲突；任何改动都需要同步更新 prompt 约束、Schema 与处理器实现。

## 记忆操作最小约束

- 操作顺序固定：`remove -> update -> refresh -> add`
- 匹配键：`content` 精确匹配
- 单项未命中：记录 WARNING，流程继续

详细数据行为统一维护在 [memory-system.md](memory-system.md#记忆操作协议)。
