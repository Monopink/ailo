# 消息发送

定义 AI 回复发送链路、打字模拟、抢占中断与失败语义。

## 数据模型

### ai_conversation_state

- `pending_messages`: 抢占导致未发送的 `outgoing` 消息片段
- `interrupted_at`: 最近一次被内容输入抢占的时间

### ai_conversation_runtime

- `ingress_version`: 内容输入入站代次，`CONTENT_INPUT` 到达即单调递增
- `active_turn_version`: 活跃处理代次，仅在新窗口到期并锁定后推进

### ai_conversation_items

- assistant timeline 消息写入成功后逐条写入

### message_history / message_dispatch_outbox / message_deliveries

- 出站消息事实与投递重试链路
- `message_dispatch_outbox` 是 timeline 发送恢复入口

## 核心语义

### 事件语义

- `CONTENT_INPUT`：文本、图片、音频等内容型输入
- `INPUT_HINT`：`typing_start`、`typing_end`

### 中断语义

- 仅 `CONTENT_INPUT` 触发抢占流程
- `CONTENT_INPUT` 到达时只推进 `ingress_version`，不立即中断当前发送
- 新窗口到期并锁定后，推进 `active_turn_version`，旧代次发送在下一检查点中断
- `INPUT_HINT` 不触发中断

### 代次语义

- 发送任务绑定 `task_turn_version=active_turn_version`
- 发送关键点检查 `current_active_turn_version == task_turn_version`
- 不一致即终止旧代次发送

### 首条发送门槛

门槛定义：当 `should_reply=true` 且存在 assistant 文本发送时，首条 assistant 文本必须满足以下条件：

1. 已写入 `message_history`
2. 已写入 `message_dispatch_outbox`
3. 已写入 `ai_conversation_items`

`finalize_buffer_if_locked(... -> COMPLETE)` 与以上三项在同一事务提交。

会话副作用（`memory_operations`、`score`）在门槛达成后执行，且两项独立提交。

### pending_messages 语义

- 仅记录抢占导致未发送片段
- 结构：

```json
{
  "outgoing": ["..."],
  "total_pending": 2
}
```

## 发送流程

### 1. 启动发送任务

输入：

- `outgoing_messages`
- `followup_messages`
- `task_turn_version`

### 2. 发送 outgoing_messages

每条消息执行：

1. 代次检查
2. 发送 `typing_start`（realtime best-effort）
3. 等待打字时长
4. 再次代次检查
5. 写入 TEXT 的 `message_history`
6. 写入 `message_dispatch_outbox`
7. 写入对应 `ai_conversation_items`
8. 若为首条 assistant 文本，在同一事务内执行 `finalize_buffer_if_locked(... -> COMPLETE)`

### 3. 等待 followup_delay_ms

等待期间保持代次检查。

### 4. 发送 followup_messages

流程与 outgoing 一致。

### 5. 收尾

- 全部完成：清空 `pending_messages`
- 抢占中断：写入未发送片段到 `pending_messages`
- 首条门槛未达成的失败/抢占：buffer 终态为 `CANCELLED`

## 中断处理

### 中断触发

- 新 `CONTENT_INPUT` 到达并提升 `ingress_version`
- 新窗口到期并锁定后，`active_turn_version` 提升

### 中断行为

1. 停止旧 `task_turn_version` 后续发送
2. 写入未发送 `outgoing` 到 `pending_messages`
3. 记录 `interrupted_at`

### 下轮处理

- `pending_messages` 通过 `{{pending_messages}}` 占位符注入到系统提示

## should_reply=false

- 不发送任何消息
- 清空 `pending_messages`

## 失败处理

### 抢占中断（并发路径）

- 写入 `pending_messages`
- 本轮终止

### Typing 扇出失败（realtime 路径）

- 失败仅记录日志
- 不中断 timeline 主流程

### Provider 投递失败（投递失败）

- 消息事实已在 `message_history` / `outbox`
- 由 outbox 重试链路处理
- 不写 `pending_messages`

详见：`docs/spec/message/failure-handling.md`

### 会话副作用失败

- 会话副作用在独立事务边界内回滚失败项
- 已发送消息事实保持不变
- 失败项记录日志用于后续排查

## 打字速度计算

### 参数

- 来源：`ai_instances.typing_speed_wpm`
- 单位：词/分钟
- 默认值：35（配置缺失或 <= 0 时记录 WARNING 并使用该固定值）

### 词数规则

- 1 全角字符 = 1 词
- 3 半角字符 = 1 词
- 1 emoji = 1 词

### 公式

```txt
秒/词 = 60 / typing_speed_wpm
总耗时（秒）= 秒/词 * 词数
```

## 并发约束

- 同会话仅允许一个当前代次发送路径
- 抢占通过 `active_turn_version` 完成跨实例一致性控制
- 不依赖进程内发送任务状态字典
