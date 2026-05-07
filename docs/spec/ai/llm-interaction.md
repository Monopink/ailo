# LLM 交互

本文档只记录 LLM 调用链路的规则与边界，不重复字段字典和子系统实现细节。

## 职责边界

- 本文档：请求参数合并、流式调用、抢占、L0/L1 校验闸门、重试、请求追踪，输出字段契约。
- 端到端编排：见 [conversation-flow.md](conversation-flow.md)。
- 涉及数据表：`llm_providers`, `llm_configs`, `llm_test_logs`, `ai_request_logs`。

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
进入 attempt 循环（仅 LLM 调用与校验）
  ↓
发起请求（流式或非流式）
  ↓
监听抢占信号
  ↓
接收完整响应 + JSON 解析
  ↓
L0 最小契约校验（硬门槛）
  ↓
L1 字段手工校验与裁剪（非硬门槛）
  ↓
落库本次 attempt（ai_request_logs）
  ↓
进入响应处理
```

流程要点：

- attempt 循环仅覆盖 LLM 调用、解析、L0/L1 校验与 attempt 落库；Prompt 构建与上下文查询不随重试重复执行。
- attempt 上限与 backoff 由 `ai_llm_min_contract_retry_*` 配置控制；缺失或类型错误按配置错误 fail-fast。
- 检测到 `active_turn_version` 切换时，当前请求必须中止并停止后续重试。
- 仅 L0 校验通过的响应才允许进入后续处理；L1 校验失败按字段整项丢弃。
- 重试间隔使用固定 backoff（`ai_llm_min_contract_retry_backoff_ms`），等待前后均执行抢占校验。
- 响应返回后、副作用执行前必须再次执行抢占校验。
- 抢占是并发控制的正常路径，不属于业务异常。

## 响应处理

LLM 响应的字段语义、处理顺序和跨模块归属见本文档的“系统识别字段”和“处理顺序”章节。

## 请求追踪与日志

为保证可审计性，调用链路必须满足：

- 每个 attempt 都写入一条 `ai_request_logs`。
- 仅最终成功且产生 assistant 文本发送的 attempt 才生成 `llm_request_id` 并绑定 `message_history.llm_request_id`。
- `ai_request_logs` 的写入入口保持唯一（`conversation_flow` 层）。
- `response_time` 按 attempt 独立记录，不做跨 attempt 累计。
- `request` / `response` 保存完整载荷与原始响应（JSONB），敏感字段必须脱敏。

字段清单与类型以模型真相源为准，本文涉及核心表：`ai_request_logs`。

## 错误边界

- 调用失败（网络、Provider、超时）：标记当前 attempt 失败并进入重试；到达上限后按静默失败处理。
- JSON 解析失败或 L0 校验失败：标记当前 attempt 失败并进入重试。
- L1 校验失败：仅丢弃对应字段整项，不阻断消息发送链路。
- 抢占：`active_turn_version` 切换后立即中断当前 attempt 并停止重试，按正常并发路径处理。
- finalize 失败：按抢占路径处理，不进入发送与会话副作用。
- 响应处理失败：`should_block` 等关键安全副作用失败终止发送；`attack_detected` 的上下文排除、审计落库与风险统计更新失败仅记录 ERROR，不终止消息流程。

## 校验约束

- 请求侧（Provider structured output）：
  - 仍使用完整运行时响应 Schema（来源：`response_schema.build_response_schema(context)`）约束/引导模型输出，尽量保证“最好情况直接可用”。
  - 若 Provider/SDK 因 schema 约束导致请求失败、超时或返回不可解析内容，视为当前 attempt 失败并进入重试（若未被抢占）。
- 运行时（系统验收）：
  - 仅对 L0 最小契约执行硬门槛校验（L0-only gate）。
  - L0 字段（`attack_detected`、`should_block`、`should_reply`、`outgoing_messages`、`followup_messages`）的 `required/type` 全量由运行时 `response schema` 决定，禁止在代码中硬编码必填约束。
  - 保持分级处理：`score`、`should_update_memory`、`memory_operations` 继续按 L1 裁剪处理，不因 schema 的 `required` 配置升级为 L0 硬门槛。
  - L1 字段不进入运行时硬门槛，由编排层手工校验与裁剪（不阻断消息发送）。
- `score` 的维度集合与取值区间校验依据当前 style 维度与 personality schema 的 `minimum` / `maximum`。
- `score` 顶层 description 来源于 personality schema 的 `score.description`；缺失时使用后端 schema 注册表默认值。
- `score` 维度描述来源于 personality schema 的 `score.properties.<dimension>.description`；当该字段缺失时使用 `ai_dimensions.description` 默认值。
- `memory_operations` 校验失败时，整项记忆副作用跳过。
- L0 校验器必须是纯函数，不依赖 db/session。

## 系统识别字段

### current_state

- 类型：string
- 语义：角色当前状态补充
- 出现条件：管理员在 personality schema 中启用该字段时出现
- 处理：当前不落库，保留为扩展位

### internal_thoughts

- 类型：string
- 语义：回复前内部思考
- 出现条件：管理员在 personality schema 中启用该字段时出现
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
- 语义：记忆操作容器（`remove` / `update` / `refresh_ids` / `add`）
- 处理归属：见 [memory-system.md](memory-system.md)
- 执行入口：统一由 `memory_policy_service` 执行策略写入与写时归档治理

### score

- 类型：object（`{dimension_name: int}`）
- 语义：关系维度分数
- 处理归属：关系系统更新（见 [relationship-system.md](relationship-system.md)）

## 处理顺序

响应处理按以下固定顺序执行：

1. `attack_detected`
2. `should_block`
3. 消息发送（受 `should_reply`、`outgoing_messages`、`followup_messages` 控制）
4. 首条发送门槛检查（仅 `should_reply=true` 且有 assistant 文本发送时适用）
5. `memory_operations`
6. `score`

- 步骤 1-2 为安全副作用，按字段定义各自的失败边界处理。
- `attack_detected` 的上下文排除、审计落库与风险统计更新为 best-effort：失败记录 ERROR，不终止消息流程。
- `should_block` 状态更新失败时终止发送路径。
- 步骤 5-6 为会话副作用，按独立事务执行，单项失败仅影响该项副作用。
- `should_reply=true` 时，步骤 5-6 受首条发送门槛控制。
- `should_reply=false` 时，不发送消息；步骤 5-6 可执行，但执行前必须再次通过抢占校验。
- 会话副作用失败不改变已发送消息事实。

## 记忆操作最小约束

- 操作顺序固定：`remove -> update -> refresh_ids -> add`
- refresh 匹配键：`memory_id`（仅允许刷新 recent 记忆）
- `refresh_ids`：
  - 输入类型：`string[] | int[]`（字符串仅接受 digits-only）
  - 执行类型：服务端归一化为去重后的 `int[]`
  - 数量：每轮最多 2 条（超出部分截断）
- 单项未命中：记录 WARNING，流程继续
- 低来源强度的自动副作用不能删除 `core` 记忆，命中后记录拦截日志并继续流程

详细数据行为统一维护在 [memory-system.md](memory-system.md)。
