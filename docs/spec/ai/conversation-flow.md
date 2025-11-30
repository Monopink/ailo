# 对话流程

本文档说明 AI 对话的完整端到端流程。

## 流程概览

```
用户发送消息
  ↓
LeanCloud Webhook 接收
  ↓
消息验证和解密
  ↓
安全检测和频率限制
  ↓
写入 ai_conversation_items
  ↓
消息缓冲聚合 (buffer)
  ↓
唤醒等待 (可选)
  ↓
双计时器等待
  ↓
计时器到期，锁定窗口
  ↓
构建 Prompt
  ↓
调用 LLM
  ↓
处理响应
  ↓
更新关系分数
  ↓
发送消息
  ↓
用户收到消息
```

## 详细流程

### 阶段 1：消息接收

**入口**：LeanCloud Webhook

详见：[../message/leancloud.md](../message/leancloud.md)

**步骤**：

1. 验证 Webhook 签名
2. 解密消息内容（如果加密）
3. 提取消息元数据（msg_id、timestamp、from_peer 等）

**输出**：验证通过的消息对象

### 阶段 2：安全检测

**检测项**：

- 频率限制（防止刷屏）
- 内容安全（敏感词、违规内容）
- 用户状态（是否被封禁）

**处理**：

- 如果检测失败，拒绝消息
- 记录违规日志
- 返回错误响应

**输出**：通过检测的消息

### 阶段 3：写入对话历史

**目标**：将用户消息写入 ai_conversation_items

详见：[../message/context.md](../message/context.md)

**逻辑**：

- role = "user"
- content = 消息内容（JSONB 格式）
- is_excluded_from_context = false
- buffer_id = NULL（稍后关联）

**输出**：ai_conversation_items 记录 ID

### 阶段 4：消息缓冲

**目标**：聚合短时间内的多条消息

详见：[../message/buffer.md](../message/buffer.md)

**步骤**：

1. 查询是否存在 OPEN 窗口
2. 如果存在，更新窗口（合并消息）
3. 如果不存在，创建新窗口
4. 根据消息类型设置计时器

**输出**：ai_message_buffer 记录（OPEN 或 WAITING_WAKEUP 状态）

### 阶段 5：唤醒等待（可选）

**触发条件**：距离上次对话超过 wake_window_ms

详见：[../message/buffer.md](../message/buffer.md#唤醒机制)

**逻辑**：

- 创建 WAITING_WAKEUP 状态的 buffer
- 设置 wake_expires_at_ms
- 等待唤醒计时器到期
- 转换为 OPEN 状态

**跳过条件**：

- 初次对话
- 连续对话（在 wake_window_ms 内）

### 阶段 6：双计时器等待

**目标**：等待用户输入完成

详见：[../message/buffer.md](../message/buffer.md#双计时器机制)

**逻辑**：

- 微计时器：每条新消息重置
- 宏计时器：从 typing_start 开始计时
- 任一计时器到期即触发处理

**输出**：计时器到期信号

### 阶段 7：锁定窗口

**目标**：抢占式锁定，防止并发处理

详见：[../message/buffer.md](../message/buffer.md#到期扫描与锁定)

**逻辑**：

1. 扫描到期的 OPEN 窗口
2. 取消该会话所有旧的 OPEN/LOCKED 窗口
3. 锁定最新且到期的窗口（LOCKED 状态）

**并发控制**：

- 唯一索引保证同会话最多一个 LOCKED
- 冲突时重试

**输出**：LOCKED 状态的 buffer

### 阶段 8：构建 Prompt

**目标**：构建完整的 LLM 请求

详见：[prompt-building.md](prompt-building.md)

**步骤**：

1. 获取 personality.prompt 模板
2. 替换系统占位符
3. 替换角色占位符
4. 查询对话历史（ai_conversation_items）
5. 构建 context
6. 合并为完整 messages 数组

**输出**：完整的 LLM 请求 messages

### 阶段 9：调用 LLM

**目标**：获取 AI 响应

详见：[llm-interaction.md](llm-interaction.md)

**步骤**：

1. 获取 LLM Config
2. 发起流式请求
3. 监听抢占信号
4. 接收响应
5. 验证 JSON Schema

**抢占处理**：

- 如果新窗口抢占，立即停止读取
- 丢弃当前结果

**输出**：验证通过的 JSON 对象

### 阶段 10：处理响应

**目标**：执行 LLM 输出的各项操作

详见：[llm-interaction.md](llm-interaction.md#响应处理)

**步骤**：

1. 处理 attack_detected（标记攻击消息）
2. 处理 should_block（阻断角色）
3. 处理 memory_operations（更新记忆）
4. 处理 score（更新关系分数）
5. 标记 buffer 为 COMPLETE

**输出**：更新后的 instance 状态

### 阶段 11：更新关系分数

**目标**：计算新的关系等级

详见：[relationship-system.md](relationship-system.md)

**步骤**：

1. 分数映射（LLM 输出 → [0, 1000]）
2. 位置映射（score → position）
3. 候选收集（position → relationships）
4. 非当前关系过滤
5. 次数限制过滤
6. 优先级选择
7. 结果落地

**输出**：更新后的 ai_instance_dimensions

### 阶段 12：发送消息

**目标**：发送 AI 回复消息

详见：[message-sending.md](message-sending.md)

**步骤**：

1. 启动异步发送任务
2. 发送 outgoing_messages（逐条，模拟打字）
3. 等待 followup_delay_ms
4. 发送 followup_messages（逐条，模拟打字）
5. 写入 ai_conversation_items（每条消息独立插入）

**中断处理**：

- 如果用户发送新消息，中断发送
- 未发送的消息写入 pending_messages

**输出**：发送成功的消息

### 阶段 13：消息传递

**目标**：通过 LeanCloud 传递给用户

详见：[../message/leancloud.md](../message/leancloud.md)

**步骤**：

1. 调用 LeanCloud REST API
2. 记录 msg_id_provider_outbound
3. 更新 message_history

**失败处理**：

- 写入 message_delivery_failures
- 按策略重试

详见：[../message/failure-handling.md](../message/failure-handling.md)

## 关键决策点

### 决策点 1：是否需要唤醒等待

**条件**：距离上次对话时间 > wake_window_ms

**是**：创建 WAITING_WAKEUP buffer，等待 wake_time_ms

**否**：直接创建 OPEN buffer，进入双计时器等待

### 决策点 2：何时触发 LLM 处理

**条件**：微计时器或宏计时器到期

**微计时器**：每条新消息重置，快速响应

**宏计时器**：从 typing_start 开始，防止无限等待

### 决策点 3：是否抢占旧处理

**条件**：新窗口到期时，存在旧的 OPEN/LOCKED 窗口

**是**：取消旧窗口，锁定新窗口

**否**：直接锁定新窗口

### 决策点 4：是否回复消息

**条件**：LLM 输出 should_reply = true

**是**：发送 outgoing_messages 和 followup_messages

**否**：不发送消息，清空 pending_messages

### 决策点 5：是否更新关系

**条件**：LLM 输出 score 对象

**是**：计算新的 position 和 relationship

**否**：保持当前关系不变

## 异常流程

### 异常 1：消息验证失败

**触发**：Webhook 签名错误、消息格式错误

**处理**：

- 拒绝消息
- 记录错误日志
- 返回 4xx 错误

**影响**：消息不进入系统

### 异常 2：安全检测失败

**触发**：频率超限、内容违规、用户被封禁

**处理**：

- 拒绝消息
- 记录违规日志
- 返回错误响应

**影响**：消息不进入系统

### 异常 3：LLM 请求失败

**触发**：网络错误、API 错误、超时

**处理**：

- 记录错误日志
- 重试（可选）
- 如果最终失败，buffer 保持 LOCKED 状态

**影响**：用户不会收到回复

### 异常 4：JSON Schema 验证失败

**触发**：LLM 输出不符合 schema

**处理**：

- 记录错误日志
- 丢弃结果
- buffer 保持 LOCKED 状态

**影响**：用户不会收到回复

### 异常 5：消息发送失败

**触发**：LeanCloud API 错误、网络错误

**处理**：

- 写入 message_delivery_failures
- 写入 pending_messages
- 按策略重试

**影响**：消息延迟送达或丢失

### 异常 6：被抢占

**触发**：用户发送新消息，创建新窗口

**处理**：

- 立即停止当前处理
- 丢弃结果
- 开始处理新窗口

**影响**：旧消息的回复被丢弃，处理新消息

## 性能优化

### 优化 1：流式输出

使用 Doubao 流式 API，边接收边处理

**优势**：

- 减少首字延迟
- 支持早停（被抢占时）

### 优化 2：异步发送

消息发送使用异步任务，不阻塞主流程

**优势**：

- buffer 可以快速标记为 COMPLETE
- 支持并发发送多个会话的消息

### 优化 3：数据库索引

关键查询使用索引优化

**索引**：

- ai_message_buffer: (user_qiao_id, instance_qiao_id, aggregate_state)
- ai_conversation_items: (user_qiao_id, instance_qiao_id, created_at)
- ai_instance_dimensions: (instance_id, dimension_id)

### 优化 4：缓存

缓存频繁查询的数据

**缓存项**：

- ai_llm_configs
- ai_personalities
- ai_relationships
- system_configs

## 监控指标

### 关键指标

**延迟指标**：

- 消息接收到 buffer 创建：< 100ms
- buffer 锁定到 LLM 请求：< 200ms
- LLM 请求到响应：< 5s
- 响应处理到消息发送：< 500ms
- 端到端延迟：< 10s

**成功率指标**：

- 消息接收成功率：> 99.9%
- LLM 请求成功率：> 99%
- 消息发送成功率：> 99.5%

**业务指标**：

- 平均对话轮次
- 关系变更频率
- 攻击检测率
- 中断发生率

## 相关文档

**基础设施**：

- [../message/buffer.md](../message/buffer.md) - 消息缓冲机制
- [../message/context.md](../message/context.md) - 上下文管理
- [../message/leancloud.md](../message/leancloud.md) - LeanCloud 集成

**业务逻辑**：

- [character-lifecycle.md](character-lifecycle.md) - 角色生命周期
- [relationship-system.md](relationship-system.md) - 关系系统
- [prompt-building.md](prompt-building.md) - Prompt 构建
- [llm-interaction.md](llm-interaction.md) - LLM 交互
- [message-sending.md](message-sending.md) - 消息发送
